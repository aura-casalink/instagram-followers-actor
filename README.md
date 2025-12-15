# Instagram Followers Scraper

Apify Actor que extrae la lista de seguidores de una cuenta de Instagram usando la API privada móvil.

## ⚠️ Requisitos

Este actor requiere tokens de autenticación que debes obtener de una sesión activa de Instagram. Los tokens expiran periódicamente y necesitan ser renovados.

### Cómo obtener los tokens

1. Instala Frida en tu ordenador
2. Configura un emulador Android con la app de Instagram
3. Usa el script de Frida para capturar las cookies de sesión
4. Copia los valores de:
   - `authorization` (Bearer token)
   - `x-mid`
   - `ig-u-ds-user-id`
   - `ig-u-rur`

## 📥 Input

| Parámetro | Tipo | Requerido | Descripción |
|-----------|------|-----------|-------------|
| `user_id` | string | ✅ | ID numérico de la cuenta de Instagram |
| `authorization_token` | string | ✅ | Bearer token (formato: `Bearer IGT:2:xxxxx`) |
| `cookie_x_mid` | string | ❌ | Cookie x-mid |
| `cookie_ds_user_id` | string | ❌ | Cookie ds_user_id |
| `cookie_rur` | string | ❌ | Cookie rur |
| `max_followers` | integer | ❌ | Límite máximo de seguidores |
| `delay` | number | ❌ | Delay entre requests (default: 2s) |
| `webhook_url` | string | ❌ | URL para notificar cuando termine |

## 📤 Output

Cada follower en el dataset contiene:

```json
{
  "pk": 12345678,
  "username": "ejemplo_user",
  "full_name": "Nombre Completo",
  "is_private": false,
  "is_verified": false,
  "profile_pic_url": "https://...",
  "scraped_at": "2024-01-15T12:00:00"
}
```

## 🔗 Integración con n8n

1. Configura el `webhook_url` con tu endpoint de n8n
2. El actor enviará un POST cuando termine:

```json
{
  "event": "followers_scraped",
  "user_id": "71392995955",
  "total_followers": 10031,
  "scraped_at": "2024-01-15T12:00:00"
}
```

3. En n8n, compara con Supabase para detectar nuevos seguidores

## 🚀 Desarrollo local

```bash
# Crear entorno virtual
python -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar localmente
apify run
```

## 📝 Notas

- Los tokens de Instagram expiran. Si recibes errores 401, renueva los tokens.
- Respeta los rate limits de Instagram. El delay default de 2s es conservador.
- Este actor es para uso personal/educativo.
