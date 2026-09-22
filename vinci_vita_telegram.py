"""
vinci_vita_telegram.py
AURORA ENGINE v3.3 — Bot Telegram sender.

Esegue l'engine v3.3, formatta il report e lo invia su Telegram.
"""
import json
import os
import sys
import argparse
import urllib.request
import urllib.parse
from datetime import datetime


PLAYED_FILE = "vinci_played.json"

TELEGRAM_MESSAGE_LIMIT = 4096
TELEGRAM_SPLIT_THRESHOLD = 3800


def send_telegram_message(text, parse_mode="HTML"):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not bot_token or not chat_id:
        print("[!] Token/chat_id mancanti. Invio saltato.")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    if len(text) > TELEGRAM_MESSAGE_LIMIT:
        text = text[:TELEGRAM_MESSAGE_LIMIT - 3] + "..."

    try:
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": "true",
        }).encode("utf-8")

        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

        with urllib.request.urlopen(req, timeout=30) as response:
            print(f"[+] Messaggio Telegram inviato! ({response.status})")
            return True
    except Exception as e:
        print(f"[!] Errore invio messaggio: {e}")
        return False


def send_telegram_report_smart(text):
    if len(text) <= TELEGRAM_SPLIT_THRESHOLD:
        return send_telegram_message(text)

    mid = len(text) // 2
    split_pos = text.rfind("\n\n", 0, mid + 500)
    if split_pos < 1000:
        split_pos = mid

    part1 = text[:split_pos].rstrip()
    part2 = text[split_pos:].lstrip()

    print(f"[*] Report splittato: parte 1 ({len(part1)} char), parte 2 ({len(part2)} char)")

    ok1 = send_telegram_message(part1)
    ok2 = send_telegram_message(part2)
    return ok1 and ok2


def load_played():
    if os.path.exists(PLAYED_FILE):
        try:
            with open(PLAYED_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"note": "Registro delle sestine giocate con Aurora Engine.", "played": []}


def save_played(data):
    try:
        with open(PLAYED_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"[+] Salvato {PLAYED_FILE}")
    except Exception as e:
        print(f"[!] Errore salvataggio {PLAYED_FILE}: {e}")


def record_play_in_file(payload):
    played = load_played()
    sestinas = payload.get("sestinas", [])
    if not sestinas:
        return

    next_draw = payload.get("next_draw", {})
    concorso = next_draw.get("concorso")
    data = next_draw.get("data")
    costo = payload.get("costo_totale", 0.0)

    for p in played["played"]:
        if p.get("concorso") == concorso:
            p["sestine"] = [s["numeri"] for s in sestinas]
            p["costo_eur"] = costo
            p["data"] = data
            print(f"[*] Concorso {concorso} già presente, aggiornato.")
            save_played(played)
            return

    played["played"].append({
        "concorso": concorso,
        "data": data,
        "giocata_il": datetime.now().strftime("%d/%m/%Y"),
        "costo_eur": costo,
        "sestine": [s["numeri"] for s in sestinas],
        "note": f"Aurora Engine v3.3 — {len(sestinas)} sestine",
    })

    save_played(played)
    print(f"[+] Registrato concorso {concorso} in {PLAYED_FILE}")


def format_telegram_report(payload):
    if not payload:
        return "❌ Nessun payload."

    lines = []
    lines.append("🌅 <b>AURORA ENGINE v3.3</b>")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("")

    rendita = payload.get("rendita_mensile", 0)
    va = payload.get("valore_attuale_rendita", 0)
    lines.append(f"💎 Rendita: <b>€ {rendita:,}/mese</b>")
    lines.append(f"   Valore attuale: € {va:,.0f}")
    lines.append("")

    if payload.get("bias_analysis"):
        ba = payload["bias_analysis"]
        lines.append(f"🧪 {ba.get('health', 'N/A')}")
        if ba.get("hot_numbers"):
            lines.append(f"   Hot: {ba['hot_numbers']}")
        if ba.get("cold_numbers"):
            lines.append(f"   Cold: {ba['cold_numbers']}")
        lines.append("")

    if payload.get("regime_report"):
        h = payload["regime_report"]["health"]
        lines.append(f"🔬 {h}")
        lines.append("")

    if payload.get("bankroll_state"):
        bs = payload["bankroll_state"]
        lines.append(f"💰 <b>Bankroll:</b> €{bs['bankroll']:.2f} "
                     f"(peak €{bs['peak']:.2f})")
        lines.append(f"   ROI: {bs['roi_pct']:+.2f}% | "
                     f"Drawdown: {bs['drawdown_pct']:.2f}%")
        if bs.get("is_stopped"):
            lines.append(f"   ⚠️ <b>STOP ATTIVO</b> fino al {bs.get('stop_until')}")
        lines.append("")

    nd = payload.get("next_draw", {})
    lines.append(f"🎯 <b>PROSSIMA: Concorso N° {nd.get('concorso')}</b>")
    lines.append(f"   {nd.get('data')} · ore {nd.get('ora', '20:00')}")
    lines.append("")

    ld = payload.get("last_draw", {})
    if ld.get("numeri"):
        ns = " · ".join(str(n).zfill(2) for n in ld["numeri"])
        lines.append(f"📊 <b>ULTIMA (N° {ld.get('concorso')})</b>")
        lines.append(f"   <code>{ns}</code>")
        lines.append("")

    bm = payload.get("budget_mode", {})
    lines.append(f"🎛️ <b>BUDGET: {bm.get('mode', 'N/A')}</b>")
    if bm.get("msg"):
        lines.append(f"   {bm['msg']}")
    lines.append("")

    if payload.get("ev"):
        ev = payload["ev"]
        lines.append(f"⚡ <b>EV:</b> €{ev['ev_netto']:+.4f} "
                     f"({ev['ev_percentuale']:+.2f}%)")
        lines.append("")

    sestinas = payload.get("sestinas", [])
    if sestinas:
        costo = payload.get("costo_totale", 0)
        lines.append(f"🎲 <b>SESTINE ({len(sestinas)} · €{costo:.2f})</b>")
        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣"]
        for i, s in enumerate(sestinas):
            e = emojis[i] if i < len(emojis) else f"{i+1}."
            ns = " · ".join(str(n).zfill(2) for n in s["numeri"])
            profilo = s.get("profilo", "?")
            lines.append(f"   {e} <b>[{profilo}]</b>")
            lines.append(f"      <code>[{ns}]</code>")

            metric_parts = [
                f"Somma {s['somma']}",
                f"ACv3 {s['anti_crowd_score']:.2f}",
            ]

            share = s.get("expected_share_eur")
            if share is not None:
                metric_parts.append(f"Share €{share:,.0f}")

            lines.append("      " + " · ".join(metric_parts))

        if payload.get("portfolio_coverage"):
            lines.append("")
            lines.append(f"📊 Coverage: {payload['portfolio_coverage']:.3f}")

        lines.append("")
    else:
        lines.append("🚫 <b>SKIP MODE</b> — Nessuna sestina")
        lines.append("")

    lines.append("🌅 <i>Aurora Engine v3.3 — Super Win for Life</i>")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--no-record", action="store_true")
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()

    if args.test:
        msg = ("🌅 <b>Aurora Engine — TEST</b>\n"
               "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
               "✅ Bot configurato correttamente!")
        send_telegram_message(msg)
        return

    print("=" * 65)
    print("AURORA ENGINE v3.3 — TELEGRAM DISPATCH")
    print("=" * 65)

    try:
        from vinci_vita_engine import run_engine
    except ImportError as e:
        print(f"[!] Errore import engine: {e}")
        sys.exit(1)

    payload = run_engine()

    if not payload:
        print("[!] Payload vuoto.")
        sys.exit(1)

    if not args.no_record:
        record_play_in_file(payload)

    report = format_telegram_report(payload)

    if not args.quiet:
        print()
        print("=" * 65)
        print("REPORT HTML DA INVIARE:")
        print("=" * 65)
        print(report)
        print("=" * 65)

    print()
    print("[*] Invio report a Telegram...")
    ok = send_telegram_report_smart(report)

    if ok:
        print("[+] Report inviato con successo!")
    else:
        print("[!] Errore invio report.")
        sys.exit(1)

    print("=" * 65)
    print("COMPLETATO")
    print("=" * 65)


if __name__ == "__main__":
    main()
