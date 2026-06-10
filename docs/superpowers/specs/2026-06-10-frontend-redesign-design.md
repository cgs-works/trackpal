# Especificación de Diseño: Rediseño Premium del Frontend (Trackpal 2026)

## Metadatos
* **Fecha**: 2026-06-10
* **Tema**: Rediseño del Frontend, Integración de Tailwind CSS v4, Sistema de Temas Light/Dark e Reestructuración de Componentes
* **Registro de Diseño**: `product`
* **Dirección Visual**: Consola Premium (Estilo Linear)

---

## 1. Contexto y Objetivos

Trackpal es una plataforma SaaS multi-tenant que permite a operadores y administradores gestionar flujos de entrega de servicios basados en WhatsApp. Con el fin de elevar el producto al estándar de diseño de **2026**, se reestructura el frontend completo para adoptar una estética de alto nivel de acabado, gran velocidad de interacción y excelente legibilidad.

### Objetivos Principales:
1. **Adopción de Tailwind CSS v4** en el proyecto frontend para una estilización ágil, moderna y sin archivos de configuración sobrecargados.
2. **Soporte Completo de Light/Dark Mode** persistente en `localStorage` con transiciones suaves y detección automática de preferencias del sistema.
3. **Estructura de Layout con Sidebar Lateral Fino** (Estilo Linear/Stripe), optimizando la densidad de información y reduciendo la duplicación de código de navegación.
4. **Modularización y Simplificación de Vistas** masivas (ej. `SubscriptionsView.vue` que cuenta con 1244 líneas de código), dividiendo las responsabilidades en componentes pequeños de menos de 501 líneas de código para cumplir con las directrices de `AGENTS.md`.

---

## 2. Sistema de Diseño Visual (Linear Theme)

### Colores (Tailwind v4 Core Classes)

| Variable de Tema | Modo Claro (Light) | Modo Oscuro (Dark) | Uso Principal |
|---|---|---|---|
| `--color-bg` | `#fafaf9` (`bg-stone-50`) | `#09090b` (`bg-zinc-950`) | Fondo principal de la página |
| `--color-surface` | `#ffffff` (`bg-white`) | `#18181b` (`bg-zinc-900`) | Fondo de tarjetas, modales y formularios |
| `--color-text` | `#1c1917` (`text-stone-900`) | `#f4f4f5` (`text-zinc-100`) | Texto principal y encabezados |
| `--color-text-muted` | `#78716c` (`text-stone-500`) | `#a1a1aa` (`text-zinc-400`) | Textos secundarios y leyendas |
| `--color-border` | `#e7e5e4` (`border-stone-200`) | `#27272a` (`border-zinc-800`) | Bordes finos de separación de 1px |
| `--color-accent` | `#6366f1` (`text-indigo-500`) | `#6366f1` (`text-indigo-500`) | Color primario para botones, enlaces y focos |

### Bordes y Sombras
* **Radio de curvatura (`border-radius`)**: Estilo fino con un valor estándar de `rounded-md` (`6px`) para botones, tarjetas y campos de formulario.
* **Bordes**: Grosor fijo de `1px` (`border`) para mantener un aspecto nítido y preciso de consola.
* **Sombras (`box-shadow`)**:
  * *Modo Claro*: Sombra sutil y difusa (`shadow-sm` para rest, `shadow-md` para elevados como modales).
  * *Modo Oscuro*: Sin sombras de color gris; en su lugar, se utilizan bordes nítidos (`border-zinc-800`) y un fondo sutilmente más claro (`bg-zinc-900/50`) para crear jerarquía y profundidad.

---

## 3. Arquitectura de Componentes

Para evitar duplicar la navegación, el selector de idioma y el toggle de temas en cada una de las 5 vistas de la aplicación, reestructuraremos el sistema bajo un layout compartido.

### 3.1 `DashboardLayout.vue`
Este componente actuará como contenedor maestro para todas las vistas que requieran autenticación (`MasterDashboardView`, `TenantDashboardView`, `SubscriptionsView`, `ClientDashboardView`).

```
+--------------------------------------------------------+
|  Sidebar Fino (Ancho: 240px / 64px colapsado)          |
|  [Logo Trackpal]                                      |
|                                                        |
|  [Sección Operador: Selector de Tenant (si es Master)]|
|                                                        |
|  [Menú de Navegación]                                  |
|   - Dashboard (Principal)                              |
|   - Subscripciones                                     |
|   - Catálogo                                           |
|   - Ajustes WhatsApp                                   |
|                                                        |
|  [Sección Inferior]                                    |
|   - Selector de Idioma (ES / EN)                       |
|   - Botón ThemeToggle (Sol/Luna)                       |
|   - Información de Perfil + Botón Salir                |
+--------------------------------------------------------+
```

### 3.2 División de `SubscriptionsView.vue` (De 1244 LoC a < 450 LoC)
La vista de subscripciones se dividirá en sub-componentes independientes:
1. **`SubscriptionTable.vue`**: Renderizado de la lista de subscripciones con su estado de credenciales, botón para revelar contraseñas y acciones de administración de perfiles.
2. **`SubscriptionModal.vue`**: Formulario popup de creación y edición de subscripciones, encapsulando las más de 300 líneas de código que actualmente ocupa el formulario en el archivo original.

---

## 4. Mecánica del Sistema de Temas (Doble Capa)

La preferencia de tema se gestionará a través de un script ligero insertado en `main.js` o en el componente principal `App.vue` para evitar destellos blancos (*flash of light mode*) durante la carga de la página.

### Lógica de Inicialización:
```javascript
const savedTheme = localStorage.getItem('theme')
const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches

if (savedTheme === 'dark' || (!savedTheme && systemPrefersDark)) {
  document.documentElement.classList.add('dark')
  document.documentElement.style.colorScheme = 'dark'
} else {
  document.documentElement.classList.remove('dark')
  document.documentElement.style.colorScheme = 'light'
}
```

---

## 5. Directrices de Implementación y Código

### Do's:
* **Hacer**: Mantener todos los componentes por debajo de las 501 líneas de código.
* **Hacer**: Usar exclusivamente clases utilitarias de Tailwind CSS v4 para la estilización.
* **Hacer**: Asegurar que cada entrada interactiva (`input`, `select`, `button`) tenga un estado `:focus-visible` con anillo de color índigo (`focus-visible:ring-2 focus-visible:ring-indigo-500`).
* **Hacer**: Incluir transiciones de transición de color suaves para todos los elementos interactivos (`transition-all duration-200 ease-in-out`).

### Don'ts:
* **No hacer**: Usar sombras pesadas ni degradados de colores múltiples en el fondo.
* **No hacer**: Duplicar la barra lateral de navegación en cada vista individual.
* **No hacer**: Ignorar la preferencia del sistema operativo del usuario.

---

## 6. Estrategia de Pruebas (Test Plan)

Se verificarán los siguientes casos mediante `vitest` en la suite de pruebas del frontend:
1. El store de autenticación redirige correctamente a los dashboards según el rol (`master`, `tenant`, `client`).
2. El selector de idioma actualiza correctamente el store de `i18n`.
3. El sistema de cambio de temas escribe correctamente en `localStorage` y actualiza las clases en la etiqueta `html`.
4. El proceso de compilación (`npm run build`) se ejecuta exitosamente sin errores de sintaxis de CSS ni advertencias de importación de Tailwind.
