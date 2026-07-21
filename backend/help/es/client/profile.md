---
id: client.profile
audience: client
plans:
  - pro
channels:
  - web
module: profile
capabilities:
  - client_profile
route: /client/profile
help_targets:
  - client.profile
title: Perfil del cliente
summary: Consulta la información de perfil y del proveedor asociada a tu cuenta de Cliente.
search_tags:
  - perfil
  - nombre
  - usuario
  - teléfono
  - proveedor
synonyms:
  - datos de cuenta
  - información personal
order: 20
safe_navigation:
  route: /client/profile
  settings_category: null
related_topics:
  - client.dashboard
  - client.password
  - client.whatsapp
---

# Perfil del cliente

Perfil es una vista de solo lectura de la información asociada a tu cuenta de Cliente.

## Canal, requisitos y acciones

- **Canal:** Web. Abre Perfil desde la navegación de Cliente después de iniciar sesión.
- **Requisitos:** Tu cuenta de Cliente debe estar activa en un Tenant Pro.
- **Acciones:** Consulta tu nombre completo, usuario, teléfono cuando esté disponible, proveedor y estado. No puedes editar estos campos desde el perfil de Cliente.

## Resultados y estados

Un teléfono o proveedor vacío significa que esa información no está configurada o no está disponible. El estado activo indica que la cuenta puede usar las superficies de Cliente. Si falla la carga del perfil, usa Reintentar; no envíes formularios repetidamente porque Perfil no tiene una acción de guardado.

## Web y WhatsApp

La página Perfil web es la vista de solo lectura principal. WhatsApp puede mostrar un resumen del perfil durante una sesión de Cliente, pero WhatsApp no puede editar los campos. Pide al proveedor que corrija un nombre, teléfono o estado de acceso.

## Límite de soporte

Solo el proveedor puede actualizar la identidad y el acceso del Cliente. No compartas tu contraseña ni datos privados de tu cuenta en una solicitud de soporte.
