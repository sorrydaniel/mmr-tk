# MMR → TK konverter

Teisendab Kaitseväe **MMR**-i (proosas kirjutatud sõjalised miinimumnõuded) RKIK **TK**
mustandiks — üks kontrollitav nõue rea kohta — laseb selle rida-realt parandada ja
ekspordib päris RKIK Exceli malli.

Rakendus on ühtlasi uurimisinstrument: iga käivitus ja iga parandus salvestatakse nii, et
mudeli tööd saab mõõta.

- **Spetsifikatsioon:** [docs/SPEC.md](docs/SPEC.md)
- **Faasid ja tegemata töö:** [docs/BACKLOG.md](docs/BACKLOG.md)
- **RKIK malli struktuur:** [docs/tk_template_reference.md](docs/tk_template_reference.md)

## Olek

**Faas 1 valmis.** Faas 2 (uurimiseksport, pime pakett, käsitsi TK import, vastuste võti) ja
faas 3 (Hinda-režiim kolmele hindajale) on kirjeldatud, tabelid olemas, kood veel kirjutamata.

## Juurutamine

Railway juurutab automaatselt `main` haru igast pushist. Käsitsi juurutussammu ei ole.

Käivituskäsk (`railway.json`):

```
alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### Keskkonnamuutujad

| Nimi | Kohustuslik | Mõju |
|---|---|---|
| `DATABASE_URL` | jah | Railway annab `postgresql://`, rakendus teisendab selle ise `postgresql+psycopg://`-ks |
| `ANTHROPIC_API_KEY` | ei | Puudub → mock-konverter + kollane bänner. **Avaliku URL-i puhul tähendab see, et võõrad ei saa krediiti kulutada.** |
| `ANTHROPIC_MODEL` | ei | Vaikimisi `claude-sonnet-5-5` |
| `APP_PASSWORD` | ei, aga soovitatav | Seatud → kogu rakendus ühe jagatud parooli taga |
| `SECRET_KEY` | **jah, kui `APP_PASSWORD` on seatud** | Allkirjastab sessiooniküpsise. Puudub → luuakse igas protsessis eraldi, mis logib iga taaskäivitusel välja ja mitme tööprotsessi korral ei lase üldse sisse logida. Logitakse käivitusel ja näidatakse login-lehel. |
| `SESSION_HTTPS_ONLY` | ei | `true` lisab küpsisele `Secure`. Vaikimisi väljas, sest Railway lõpetab TLS-i oma proxy's ja rakendus ise näeb ainult HTTP-d |

Küpsis on `httponly`, `samesite=lax`, `path=/`, ilma `Domain`-ita, eluaeg 14 päeva.
Uvicorn käib **ühe tööprotsessiga** (`--workers` ei ole seatud) ja `--proxy-headers
--forwarded-allow-ips=*`-ga, nii et proxy taga on skeem ja host õiged. Kui tööprotsesse
kunagi juurde panna, peab `SECRET_KEY` olema kindlasti seatud — muidu allkirjastab iga
protsess oma võtmega ja sisselogimine ei püsi.

`/health` vastab 200 ka siis, kui andmebaas ei vasta — muidu tapaks platvormi tervisekontroll
konteineri, mis lihtsalt ootab andmebaasi.

## Arendus

Rakendus **ei käi arendaja arvutis** ja kohalikku andmebaasi ei ole. Testid kasutavad
SQLite-i mälus ja mock-konverterit, nii et neid saab jooksutada igal pool.

Enne iga pushi:

```powershell
pip install -r requirements.txt; if ($?) { pytest }; if ($?) { python -c "import app.main" }
```

## Andmepoliitika

Päris ja saniteeritud MMR/TK dokumente **ei pane kunagi gitti** — need elavad ainult
käitusaegsete üleslaadimistena Railway andmebaasis. Repos on ainult **välja mõeldud**
testandmed. Ainus erand on tühi ametlik mall `app/assets/tk_template.xlsx`, milles ei ole
ühtegi nõuet ja mis on ekspordi aluseks.
