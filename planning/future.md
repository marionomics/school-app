# Future — ideas y preguntas abiertas

Cosas deliberadamente pospuestas. Nada aquí bloquea el MVP.

## Preguntas abiertas (requieren decisión de Mario)

1. ~~**Cap / anti-cramming de likes.**~~ **RESUELTA 2026-07-30.** En vez de un cap, una curva cóncava: `puntos = like_value × N^like_exponent`, con exponente `0.5` por defecto y configurable por clase. Cada like nuevo vale menos que el anterior, así que farmear al final rinde cada vez menos sin necesidad de topes ni efectos cobra. 100 likes = 10 pts; un 10 solo con likes exige 10,000. Las participaciones siguen lineales (1 tap = 1 pt) porque ese es el comportamiento que sí se quiere premiar. Ver `docs/superpowers/specs/2026-07-30-phase-2a-tareas-y-motor-design.md` §2.3.
2. **Wiki: integrar vs construir.** Candidatos evaluados en la nota: wiki.js, DokuWiki, Docmost (soporta LaTeX), BookStack. Requisito duro: integración con el sistema de puntos (crear/editar artículos y recibir likes genera décimas; ediciones revisadas por moderador). Preferencia: escribir en MD con LaTeX. Abierta al mundo para lectura sin login; edición solo profesor + alumnos.
3. **Incentivos de moderador.** ¿Punto extra asignado directamente, o registro abierto con recompensas por acción? Moderación siempre anónima (capibara) y solo sobre clases ajenas.
4. **DMs.** "Maybe we don't really need those" vs "probablemente valga la pena para engagement". Decidir después de que existan notificaciones.
5. **Exención.** Licenciatura: ≥ 8.5 exenta ordinario; si no, ordinario se promedia. Posgrado: distinto. Definir mecánica exacta como settings de clase.

6. ~~**Quitar el aura a una participación ya validada.**~~ **RESUELTA 2026-10-09.** Sí: quitar el aura des-valida (`reviewed_at` vuelve a nulo y la participación regresa a la cola). Es el mismo hecho. Ver roadmap Bloque 2.
7. **¿Qué baja en el feed: lo que tocaste o también lo que viste?** El Bloque 4 arranca con interacciones (aura, respuesta, validación) porque ya están registradas. "Visto" necesita registrar impresiones — decidir si vale la pena después de medir la primera vuelta.

## Huecos conocidos (pequeños, con dueño claro)

- **Editar nombre, fechas y horario de la clase.** Hoy sólo se pueden fijar al crearla: `ClassSettingsUpdate` acepta pesos, valores de puntos y el mínimo de asistencia, nada más. La página `/configurar/clase` los muestra en solo lectura. Falta un endpoint; se dejó fuera del design pass a propósito porque era scope de backend que esa fase no tenía. (2026-08-02)

## Ideas de largo plazo

- **Buscador de GIFs en el compositor** (Mario, 2026-10-20). Subir un GIF propio ya funciona (se muestra animado, sin reducir). Para buscar GIFs: Tenor cerró su API el 2026-06-30; GIPHY es gratis sólo con llave beta (100 llamadas/hora, 1,000/día) y la llave de producción tiene precio a negociar desde marzo de 2025; KLIPY (ex-Tenor, la que usan Discord y WhatsApp) tiene plan gratis. Para ~40 alumnos por clase, la llave beta de GIPHY o KLIPY alcanzan si el buscador llama a la API sólo al escribir (con debounce) y el backend hace de proxy para no exponer la llave. Requiere atribución ("Powered by GIPHY"/KLIPY).
- **Premio por comentar** (Mario, 2026-10-21). Para empujar los comentarios: al comentar, con cierta probabilidad (se pensó en 20 %) el aura de ese comentario vale doble o triple. Mueve puntos, así que va en el motor y necesita su propio spec — fuera del Bloque 4. Dos cosas a decidir: (a) cada sorteo se guarda como fila del ledger en el momento, nunca se tira el dado al calcular (si no, la calificación cambia cada vez que se computa); (b) a qué se aplica el multiplicador — al aura recibida (cóncava: ×2 sobre 4 auras da +2, sobre 100 da +10) o a un punto propio por comentar. Pariente de "Salvando el semestre".
- **Wiki** con tagging `[[artículo]]` desde el foro (estilo Obsidian) y menciones `@compañero`
- **Algoritmo del feed, segunda vuelta:** prioridad a posts *no vistos* (requiere registrar impresiones, no sólo interacciones) y afinidad (interactuar con alguien sube sus posts en tu feed). La primera vuelta —bajar lo que ya tocaste— está en el roadmap, Bloque 4.
- **Asistencia criptográfica:** QR sensible al tiempo estilo 2FA, o "diseminación" de asistencia entre compañeros de al lado (autentica presencia física)
- **Tareas por nota de voz** (el profe graba la asignación)
- **Encuestas** en posts; subir directo desde la cámara
- **Modo inglés** completo (segundo archivo de strings; reto "todo en inglés" se valida con páginas del wiki en inglés)
- **Integración con Skool** para polizones/comunidad
- **App nativa** (React Native Reusables) si algún día hace falta — la API queda lista para un segundo cliente
- **FAQs** dentro de la plataforma (¿se ganan puntos en el foro durante el examen? Sí. ¿Puede un LLM aportar al wiki? Solo sobre el funcionamiento de la clase/sistema, nunca sobre contenido de economía.)
