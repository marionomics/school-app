# Future — ideas y preguntas abiertas

Cosas deliberadamente pospuestas. Nada aquí bloquea el MVP.

## Preguntas abiertas (requieren decisión de Mario)

1. **Cap / anti-cramming de likes.** Hoy: lineal, 1 like = 1 décima, sin cap (configurable en `points_config`). Deseo: castigar la acción de último momento (alumnos que solo farmean puntos al final) sin generar efectos cobra. Opciones consideradas: cap semanal, cap semestral (~20), escala con umbrales (1/5/15/35/75 likes). Decidir con datos reales de uso.
2. **Wiki: integrar vs construir.** Candidatos evaluados en la nota: wiki.js, DokuWiki, Docmost (soporta LaTeX), BookStack. Requisito duro: integración con el sistema de puntos (crear/editar artículos y recibir likes genera décimas; ediciones revisadas por moderador). Preferencia: escribir en MD con LaTeX. Abierta al mundo para lectura sin login; edición solo profesor + alumnos.
3. **Incentivos de moderador.** ¿Punto extra asignado directamente, o registro abierto con recompensas por acción? Moderación siempre anónima (capibara) y solo sobre clases ajenas.
4. **DMs.** "Maybe we don't really need those" vs "probablemente valga la pena para engagement". Decidir después de que existan notificaciones.
5. **Exención.** Licenciatura: ≥ 8.5 exenta ordinario; si no, ordinario se promedia. Posgrado: distinto. Definir mecánica exacta como settings de clase.

## Ideas de largo plazo

- **Wiki** con tagging `[[artículo]]` desde el foro (estilo Obsidian) y menciones `@compañero`
- **Algoritmo del feed:** prioridad a posts no vistos; afinidad (interactuar con alguien sube sus posts en tu feed)
- **Asistencia criptográfica:** QR sensible al tiempo estilo 2FA, o "diseminación" de asistencia entre compañeros de al lado (autentica presencia física)
- **Tareas por nota de voz** (el profe graba la asignación)
- **Encuestas** en posts; subir directo desde la cámara
- **Modo inglés** completo (segundo archivo de strings; reto "todo en inglés" se valida con páginas del wiki en inglés)
- **Integración con Skool** para polizones/comunidad
- **App nativa** (React Native Reusables) si algún día hace falta — la API queda lista para un segundo cliente
- **FAQs** dentro de la plataforma (¿se ganan puntos en el foro durante el examen? Sí. ¿Puede un LLM aportar al wiki? Solo sobre el funcionamiento de la clase/sistema, nunca sobre contenido de economía.)
