# Bloque 3a — Fotos: imágenes en línea y foto de perfil

**Estado:** diseño aprobado por Mario el 2026-10-19, sección por sección. Roadmap Bloque 3 ("Fotos primero").

## Objetivo

A veces un alumno se expresa mejor con una foto. Hoy una imagen adjunta aparece como un enlace que hay que abrir; debe verse en la publicación, como en una red social. Éxito: un alumno publica una foto desde su teléfono y todos la ven en el feed al instante, en cualquier teléfono, sin acabarse sus datos móviles. Y cada quien puede poner su propia foto de perfil.

## Decisiones (Mario)

1. **Se reduce una vez y no se guarda el original** (opción B). Para que la letra a mano siga legible al calificar, el tamaño es generoso: **2048 px de lado mayor**, JPEG calidad 0.85 (≈ 400–700 KB). Nunca se agranda.
2. **Se reduce en el teléfono, antes de subir** (opción A). Sube menos datos, y el iPhone convierte su HEIC a JPEG en el camino — el HEIC que Android no puede mostrar desaparece en el origen.
3. **El profesor puede quitar la foto de perfil de cualquier alumno** (opción A): excepción, no cola de aprobación. El alumno regresa a su foto de Google y puede subir otra.
4. **Las fotos ya subidas también se ven en línea**, sin migrar nada en R2 (son pocas, aunque pesen el original).
5. **La bio ya existe** (se edita en `/onboarding`); mostrarla a otros es la página de perfil `/u/:username`, spec aparte inmediatamente después de éste.

## 1. Subida

### `frontend/src/lib/images.ts` (imports relativos — tiene test)
- `fitWithin(w, h, max): { width, height }` — reduce proporcionalmente si el lado mayor pasa de `max`; si no, devuelve lo mismo. Pura.
- `centerSquare(w, h): { sx, sy, size }` — el recorte cuadrado central. Pura.
- `shouldShrink(file): boolean` — `true` para `image/jpeg`, `image/png`, `image/webp`, `image/heic`, `image/heif` (o extensión `.heic/.heif` con `type` vacío); `false` para GIF (perdería la animación), SVG y todo lo que no sea imagen. Pura.
- `shrinkImage(file, max = 2048): Promise<File>` — si `shouldShrink`, decodifica con `createImageBitmap(file, { imageOrientation: "from-image" })`, pinta el canvas de blanco (un PNG con transparencia saldría con fondo negro en JPEG), dibuja a `fitWithin(...)` y codifica `image/jpeg` a 0.85, con nombre `<base>.jpg`. Devuelve el **original** si: no aplica, el navegador no puede decodificar (HEIC en Chrome de escritorio), falla cualquier paso, o el resultado pesa más que el original **y el original es JPEG, PNG o WebP** — un HEIC siempre se entrega convertido, aunque el JPEG pese más, porque un HEIC no se ve en Android.
- `squareAvatar(file, size = 512): Promise<File>` — igual, recortando con `centerSquare` y escalando a `size`×`size`.

**Efectos:** volver a codificar borra los metadatos — incluida la **ubicación GPS** de la foto (una foto tomada en casa ya no dice dónde vive el alumno) — y aplica la orientación (las fotos de lado salen derechas).

### Dónde corre
Todo selector de archivos — compositor, formulario de respuesta, entregas — pasa por un helper `prepareFiles(files: File[]): Promise<File[]>` (en `images.ts`) antes de `addFiles`. Mientras trabaja, el selector muestra "Preparando foto…" y el botón de publicar espera. Un fallo cae al original en silencio.

### Backend
Sin cambios en la subida de publicaciones: mismo tope de 10 MB, mismas extensiones, mismo `create_post`. El servidor nunca confía en que el cliente redujo nada. Sin migración para fotos de publicaciones (no se guardan dimensiones; el diseño de la sección 2 no las necesita).

## 2. Cómo se ven

### Backend
- `AttachmentOut` gana `url: Optional[str]`: un enlace firmado de R2 **válido una hora** (`storage.generate_presigned_url`, firma local sin llamada de red) para adjuntos mostrables — `mime_type` en `image/jpeg`, `image/png`, `image/webp`, `image/gif`. HEIC, SVG y no-imágenes: `url = None` (siguen como chip). Sin R2 configurado: `url = None`.
- Un helper `attachment_out(att) -> AttachmentOut` en un solo lugar; lo usan `serialize_post` y el roster de exámenes.
- Publicación borrada: sigue sin adjuntos. Vetada: conserva sus fotos, como su texto.
- El roster de `/revisar → Exámenes` (`submission.attachments`) incluye el mismo `url`.

### Frontend: `components/PostPhotos.tsx`
Usado por `PostCard` y por `ExamenRoster`.
- **1 foto:** ancho completo, caja fija **4:5**, foto entera visible (`object-contain`) sobre fondo gris claro. Fija para que el feed no salte al cargar; sin recorte para no partir una página de tarea.
- **2–4 fotos:** cuadrícula de 2 columnas con mosaicos cuadrados recortados (`object-cover`).
- **Tocar** abre la foto entera a pantalla completa en el `Dialog` preset, con anterior/siguiente si hay varias. Cerrar regresa al mismo lugar del feed.
- Marcador gris mientras carga; `loading="lazy"` y `decoding="async"`.
- **Enlace caducado** (pestaña abierta más de una hora): en `onError`, una sola vez, pide `/api/attachments/{id}/url` y reintenta con el nuevo.
- `alt` desde el módulo de strings: "Foto de @{user}" (provisional). Sin pies de foto.
- La lógica de qué diseño corresponde a N fotos es una función pura (`photoLayout(n)`) en `src/lib`.
- Los adjuntos que no son imagen siguen como chips debajo de las fotos.

## 3. Foto de perfil

### Backend
- **Migración:** `users.avatar_key` (`String(500)`, nullable). `users.avatar_url` (la de Google, fijada al crear la cuenta) se queda como respaldo.
- **Un helper `avatar_for(user) -> Optional[str]`**: enlace firmado de una hora a `avatar_key` si existe y R2 está configurado; si no, `avatar_url`. Todo esquema que expone `avatar_url` de un usuario (`AuthorOut`, `UserOut`, filas de roster en `classes.py` y `grades.py`) lo obtiene de este helper — el frontend no cambia de campo.
- `PUT /api/users/me/avatar` (multipart, un archivo `file`): sólo `image/jpeg`, `image/png`, `image/webp`; máximo 10 MB; si no, 422. Sin R2: 400. Sube a `avatars/{user_id}_{timestamp}.jpg`, fija `avatar_key`, devuelve `UserOut`.
- `DELETE /api/users/me/avatar`: `avatar_key = NULL`; devuelve `UserOut`.
- `DELETE /api/users/{user_id}/avatar`: sólo un profesor, y sólo si ese usuario tiene una inscripción en alguna clase que él imparte; si no, 403. Mismo efecto.
- Las fotos reemplazadas no se borran de R2 (pesan poco).

### Frontend
- En `/onboarding` (donde ya se editan username y bio; el ícono "perfil" de la barra lleva ahí): la foto actual con **Cambiar foto** y, si subió una propia, **Quitar foto**. Elegir una foto la recorta al cuadrado central y la reduce a 512 px (`squareAvatar`), muestra la vista previa y se guarda con **Guardar**. Optimista con rollback visible.
- El **Quitar foto** del profesor vive por ahora en la hoja del alumno del panel de clase (la misma que lista sus faltas); se muda al perfil cuando exista `/u/:username`.
- `Avatar`: si la imagen falla (enlace caducado), cae a la inicial en lugar de mostrar una imagen rota.

## 4. Tests

**Backend** (primero; R2 sustituido por un stub que registra subidas y devuelve enlaces firmados predecibles — los tests nunca hablan con Cloudflare):
- Un adjunto imagen trae `url`; un PDF no; HEIC y SVG no.
- Publicación borrada: sin adjuntos; vetada: los conserva con `url`.
- El roster de exámenes trae `url` en `submission.attachments`.
- Subir foto fija `avatar_key` y el `avatar_url` de ese usuario es el enlace firmado en `/me`, en el feed (`author`) y en el roster de clase.
- Quitar foto regresa a la de Google.
- PDF o archivo de más de 10 MB → 422.
- Un alumno no puede quitar la foto de otro (403); el profesor sí, sólo la de alumnos de su clase (otro → 403).
- Migración: agregar la columna conserva el `avatar_url` de Google de los usuarios existentes.

**Frontend:** `fitWithin` (sólo reduce, conserva proporción, vertical y horizontal), `centerSquare`, `shouldShrink` (GIF, SVG, no-imagen → false; HEIC sin `type` → true), `photoLayout(n)`. Tipos, lint, build. QA en el teléfono tras desplegar: foto HEIC de iPhone visible en Android, página escrita a mano legible al tocarla, cambio de foto de perfil visible en todos lados.

## Orden de commits (cada uno desplegable)

1. Backend: `url` en adjuntos imagen (`attachment_out`) + roster.
2. Frontend: `PostPhotos` + visor a pantalla completa — las fotos ya subidas se ven en línea desde aquí.
3. Frontend: `images.ts` reduciendo en todo selector de archivos.
4. Backend: `avatar_key` + migración + `avatar_for` + los tres endpoints.
5. Frontend: cambiar/quitar foto en `/onboarding`, el botón del profesor en el panel, el respaldo de `Avatar`.

## Fuera de alcance

- La página de perfil `/u/:username` (bio visible, aura recibida, publicaciones) — spec siguiente.
- Editor de recorte arrastrable; pies de foto por imagen; reducir las fotos ya subidas en R2; borrar de R2 las fotos de perfil reemplazadas.
