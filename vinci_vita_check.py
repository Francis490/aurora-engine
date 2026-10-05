"""
vinci_vita_check.py
AURORA ENGINE v5.5 — Check post-estrazione automatico.

Verifica le sestine giocate contro l'ultima estrazione disponibile.
Aggiorna vinci_played.json e vinci_bankroll.json (se c'è vincita).
Invia Telegram con il risultato.

FIX (2026-10-05):
- #8: esito usa il risultato BEST (max punti), non results[0].
  Prima prendeva i numeri_centrati della prima sestina anche quando
  il punteggio massimo era di un'altra.
- #9: bankroll aggiornato PRIMA di marcare esito_verificato=True.
  Prima l'ordine era invertito: se record_win() falliva, la vincita
  non veniva mai accreditata perché il flag era già True.
  Ora se il bankroll fallisce, l'esito NON viene marcato come verificato
  e il check verrà ritentato al prossimo run.

FIX (2026-10-01):
- Warning retroattivo: se giocata_il > data_estrazione, salta (falso positivo).
- Allineato a v5.5.
"""
import json
import os
import sys
import argparse
import urllib.request
import urllib.parse
from datetime import datetime


HISTORY_FILE = "vinci_history.json"
PLAYED_FILE = "vinci_played.json"

DATABASE_VERSION = "5.5"


def load_json(fp, default):
    if os.path.exists(fp):
        try:
            with open(fp, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[!] Errore lettura {fp}: {e}")
    return default


def save_json(fp, data):
    try:
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"[+] Salvato {fp}")
    except Exception as e:
        print(f"[!] Errore salvataggio {fp}: {e}")


def send_telegram_message(text, parse_mode="HTML"):
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not bot_token or not chat_id:
        print("[!] Token/chat_id mancanti, salto Telegram.")
        return False
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    if len(text) > 4000:
        text = text[:3997] + "..."
    try:
        data = urllib.parse.urlencode({
            "chat_id": chat_id, "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": "true",
        }).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with urllib.request.urlopen(req, timeout=30) as response:
            print(f"[+] Telegram: {response.status}")
            return True
    except Exception as e:
        print(f"[!] Errore Telegram: {e}")
        return False


def _premio_for_punti(punti):
    try:
        from vinci_vita_math import premio_stimato
        return float(premio_stimato(punti))
    except Exception as e:
        print(f"[!] Impossibile importare premio_stimato: {e}")
        fallback = {0: 0.0, 1: 0.0, 2: 5.0, 3: 25.0, 4: 250.0, 5: 25000.0}
        return fallback.get(punti, 0.0)


def _format_punti(punti, numeri_centrati):
    if punti == 0:
        return "0 punti"
    if punti == 1:
        return f"1 punto ({', '.join(str(n).zfill(2) for n in numeri_centrati)})"
    return f"{punti} punti ({', '.join(str(n).zfill(2) for n in numeri_centrati)})"


def check_draw_against_played(concorso, numeri_estratti, sestine):
    estratti_set = set(numeri_estratti)
    results = []
    for s in sestine:
        s_set = set(s)
        comuni = sorted(s_set & estratti_set)
        punti = len(comuni)
        premio = _premio_for_punti(punti) if punti >= 2 else 0.0
        results.append({
            "sestina": list(s),
            "punti": punti,
            "numeri_centrati": comuni,
            "premio_eur": round(premio, 2),
        })
    return results


def _build_telegram_report(concorso, data_str, numeri_estratti,
                           results, totale_premio, costo_totale):
    lines = []
    lines.append(f"🏁 <b>CHECK POST-ESTRAZIONE</b>")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("")
    lines.append(f"📅 <b>Concorso N° {concorso}</b> · {data_str}")
    ns = " · ".join(str(n).zfill(2) for n in numeri_estratti)
    lines.append(f"🎰 Estratti: <code>{ns}</code>")
    lines.append("")
    lines.append(f"🎯 <b>Sestine giocate: {len(results)}</b>")
    lines.append("")

    for i, r in enumerate(results, 1):
        s_ns = " · ".join(str(n).zfill(2) for n in r["sestina"])
        lines.append(f"   {i}. <code>[{s_ns}]</code>")
        lines.append(f"      {_format_punti(r['punti'], r['numeri_centrati'])}")
        if r["premio_eur"] > 0:
            lines.append(f"      💰 €{r['premio_eur']:.2f}")
        lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    if totale_premio > 0:
        netto = totale_premio - costo_totale
        lines.append(f"💎 <b>VINCITA: €{totale_premio:.2f}</b>")
        lines.append(f"   (netto: €{netto:+.2f})")
    else:
        lines.append(f"😔 <b>Nessuna vincita</b>")
        lines.append(f"   (speso: €{costo_totale:.2f})")
    lines.append("")
    lines.append(f"🌅 <i>Aurora Engine v{DATABASE_VERSION}</i>")
    return "\n".join(lines)


def run_check(force=False, quiet=False):
    print("=" * 65)
    print(f"AURORA ENGINE v{DATABASE_VERSION} — CHECK POST-ESTRAZIONE")
    print("=" * 65)

    history = load_json(HISTORY_FILE, [])
    played = load_json(PLAYED_FILE, {"note": "", "played": []})

    if not history:
        print("[*] Nessuna estrazione in history. Skip.")
        return None

    if not played.get("played"):
        print("[*] Nessuna giocata registrata. Skip.")
        return None

    last_draw = history[-1]
    concorso = last_draw.get("concorso")
    numeri_estratti = last_draw.get("numeri", [])
    data_str = last_draw.get("data", "—")

    if not concorso or len(numeri_estratti) != 8:
        print("[*] Ultima estrazione senza dati validi. Skip.")
        return None

    print(f"[*] Ultima estrazione: Concorso {concorso} · {data_str}")
    print(f"[*] Numeri: {numeri_estratti}")

    played_entry = None
    for p in played["played"]:
        if p.get("concorso") == concorso:
            played_entry = p
            break

    if not played_entry:
        print(f"[*] Nessuna giocata per il concorso {concorso}. Skip.")
        return None

    if played_entry.get("esito_verificato") and not force:
        print(f"[*] Concorso {concorso} già verificato. Skip.")
        return None

    # Warning retroattivo anti-falso-positivo
    giocata_il = played_entry.get("giocata_il", "")
    try:
        d_giocata = datetime.strptime(giocata_il, "%d/%m/%Y")
        d_estrazione = datetime.strptime(data_str, "%d/%m/%Y")
        if d_giocata > d_estrazione:
            print(f"[!!!] ATTENZIONE: giocata registrata il {giocata_il} "
                  f"MA estrazione del {data_str}.")
            print(f"[!!!] Falso positivo. Salto verifica.")
            return None
    except (ValueError, TypeError):
        pass

    sestine = played_entry.get("sestine", [])
    if not sestine:
        print(f"[*] Concorso {concorso} senza sestine. Skip.")
        return None

    print(f"[*] Verifico {len(sestine)} sestine...")

    results = check_draw_against_played(concorso, numeri_estratti, sestine)
    totale_premio = sum(r["premio_eur"] for r in results)
    costo_totale = played_entry.get("costo_eur", len(sestine) * 2.0)

    print()
    for i, r in enumerate(results, 1):
        print(f"  {i}. {r['sestina']} → {r['punti']} punti, €{r['premio_eur']:.2f}")

    print()
    print(f"[*] Totale premio: €{totale_premio:.2f}")
    print(f"[*] Costo:         €{costo_totale:.2f}")
    print(f"[*] Netto:         €{totale_premio - costo_totale:+.2f}")

    # ========================================
    # FIX #9: aggiorna bankroll PRIMA di salvare esito_verificato=True
    # ========================================
    bankroll_ok = True
    if totale_premio > 0:
        try:
            from vinci_vita_bankroll import BankrollManager
            bm = BankrollManager()
            bm.record_win(totale_premio, note=f"Concorso {concorso}")
            print(f"[+] Bankroll aggiornato: +€{totale_premio:.2f}")
        except Exception as e:
            print(f"[!] Errore bankroll: {e}")
            bankroll_ok = False
    else:
        print("[*] Nessuna vincita da accreditare.")

    # ========================================
    # FIX #8: usa il risultato BEST (max punti), non results[0]
    # ========================================
    if bankroll_ok:
        best = max(results, key=lambda r: r["punti"]) if results else None
        played_entry["esito"] = _format_punti(
            best["punti"] if best else 0,
            best["numeri_centrati"] if best else []
        )
        played_entry["punti_per_sestina"] = [r["punti"] for r in results]
        played_entry["premio_reale"] = round(totale_premio, 2)
        played_entry["esito_verificato"] = True
        played_entry["esito_verificato_il"] = datetime.now().isoformat()
        save_json(PLAYED_FILE, played)
    else:
        print("[!] Bankroll NON aggiornato. Esito NON marcato come verificato.")
        print("[!] Il check verrà ritentato al prossimo run.")
        return {
            "concorso": concorso,
            "results": results,
            "totale_premio": totale_premio,
            "netto": totale_premio - costo_totale,
            "bankroll_ok": False,
        }

    if not quiet:
        report = _build_telegram_report(
            concorso, data_str, numeri_estratti,
            results, totale_premio, costo_totale
        )
        print()
        print("[*] Invio Telegram...")
        send_telegram_message(report)

    print("=" * 65)
    return {
        "concorso": concorso,
        "results": results,
        "totale_premio": totale_premio,
        "netto": totale_premio - costo_totale,
        "bankroll_ok": True,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    run_check(force=args.force, quiet=args.quiet)


if __name__ == "__main__":
    main()
