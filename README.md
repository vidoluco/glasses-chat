# glasses-chat: un assistente con la camera dei Ray-Ban Meta, via WhatsApp

Gli occhiali mandano foto e domanda al contatto **Tony** su WhatsApp. Il bot risponde e gli occhiali leggono la risposta ad alta voce.

```
occhiali ─WhatsApp─▶ Meta ─webhook─▶ relay (Cloudflare) ◀─pull─ bridge.py (Mac) ─▶ Codex
                                                                      │
occhiali ◀─WhatsApp─ Meta ◀──────────────── risposta ─────────────────┘
```

Il Mac non apre porte verso internet: è il bridge a interrogare il relay.

## Uso

| Dici agli occhiali | Succede |
|---|---|
| "Hey Meta, take a photo and send it to Tony" | la foto aspetta la domanda per 20 secondi |
| "Hey Meta, send a message to Tony saying …" | risposta sulla foto, se arriva entro 90 secondi; altrimenti risposta senza foto |
| solo la foto | dopo 20 secondi risponde a "Cosa sto guardando?" |

## Account, una volta sola

1. **Meta for Developers** (developers.facebook.com): crea un'app di tipo Business e aggiungi il prodotto WhatsApp.
2. In **WhatsApp > API Setup** annota il *Phone number ID* del numero di test e aggiungi il tuo numero tra i destinatari (arriva un codice su WhatsApp).
3. In **App settings > Basic** annota l'*App Secret*.
4. Salva in rubrica il numero di test con il nome **Tony** (un nome corto, facile da dire agli occhiali).
5. **Cloudflare**: account gratuito, poi `npx wrangler login`.

Il token di accesso di API Setup dura 24 ore: va bene per la prima prova. Per l'uso quotidiano serve un token permanente di un *System user* in Business Settings, con i permessi `whatsapp_business_messaging`.

## Relay

```
cd relay
npx wrangler deploy
npx wrangler secret put APP_SECRET     # App Secret di Meta
npx wrangler secret put VERIFY_TOKEN   # una stringa a caso, serve al passo dopo
npx wrangler secret put PULL_TOKEN     # un'altra stringa a caso, la usa il bridge
npx wrangler secret put ALLOWED_FROM   # il tuo numero senza +, es. 15550001111
```

In **WhatsApp > Configuration** imposta Callback URL `https://heychat-relay.<account>.workers.dev/webhook` e il Verify token, poi abilita il campo `messages`.

## Bridge sul Mac

`~/.config/glasses-chat/whatsapp.json`, con permessi 600:

```json
{
  "relay_url": "https://heychat-relay.<account>.workers.dev",
  "pull_token": "<PULL_TOKEN>",
  "whatsapp_token": "<token di Meta>",
  "phone_number_id": "<Phone number ID>"
}
```

```
cd server && python3 bridge.py
```

## Test

```
cd server && python3 -m unittest test_bridge     # 11 test
node --test relay/worker.test.mjs               # 6 test
```
