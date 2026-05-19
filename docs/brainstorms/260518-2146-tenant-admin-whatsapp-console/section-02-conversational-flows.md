# Conversational Flows - Tenant Admin WhatsApp Console

All user-facing text in Spanish.

## Main Menu

```
*Trackpal Admin Console*

?Que deseas gestionar?

1? Clientes
2? Catalogo
3? Mi Perfil
4? Ayuda

0? Salir
```

## Clients Flow

### List clients

```
*Clientes* (3)
1. Juan Perez - ? Activo
2. Maria Garcia - ? Inactivo
3. Carlos Lopez - ? Activo

Selecciona un numero para ver detalle,
? escribe "+" para crear nuevo,
0? Volver
```

**Edge cases**:
- 0 clients: "No tienes clientes registrados. Escribe + para crear uno."
- Inactive shows "(Inactivo)" suffix
- 9+ clients: all listed (WhatsApp supports scroll)

### Client detail

```
*Juan Perez*
Telefono: +521234567890
Email: juan@ejemplo.com
Usuario: juan_perez
Estado: ? Activo

1? Editar
2? Desactivar
3? Eliminar
0? Volver
```

### Edit client

```
?Que deseas editar?

1? Nombre completo
2? Email
3? Telefono
4? Usuario local
0? Cancelar
```

Then: `Seleccionaste: Nombre completo. Ingresa el nuevo valor:`

Validation error: `El nombre debe tener entre 2 y 200 caracteres. Intenta de nuevo:`

Success: `Nombre actualizado a: Juan Carlos Perez`

### Create client (wizard)

```
Paso 1/6 -> ?Nombre completo del cliente?
Paso 2/6 -> ?Email del cliente?
Paso 3/6 -> ?Telefono del cliente? (opcional - escribe "skip" para omitir)
Paso 4/6 -> ?Nombre de usuario local para el cliente?
Paso 5/6 -> ?Contrasena? (opcional - escribe "auto" para generar automaticamente)
Paso 6/6 -> Confirma los datos:
  Nombre: Juan Perez
  Email: juan@ejemplo.com
  Telefono: +521234567890
  Usuario: juan_perez
  Contrasena: [auto-generada]

?Todo correcto? Escribe CONFIRMAR o 0 para cancelar.
```

### Deactivate client

```
?DESACTIVAR a Juan Perez?
Esto inhabilitara su acceso.

Escribe CONFIRMAR para continuar,
0? Cancelar
```

### Reactivate client

(Immediate, no confirmation)

```
?Cliente reactivado.
```

### Delete client

```
?ELIMINAR a Juan Perez?
Esta accion NO se puede deshacer.
El cliente debe estar inactivo.

Escribe CONFIRMAR para continuar,
0? Cancelar
```

Error if active: `No se puede eliminar: el cliente esta activo. Desactivalo primero.`

## Catalog Flow

### List services

```
*Catalogo - Servicios*
1. Corte de Cabello
2. Manicure
3. Pedicure

Selecciona un numero para ver detalle,
0? Volver
```

### Service detail + plans

```
*Corte de Cabello*
Descripcion: Corte clasico y moderno
Estado: ? Activo

*Planes:*
1. Corte Dama - $250.00
2. Corte Caballero - $180.00

Selecciona un plan para ver detalle,
1? Editar nombre del servicio
2? Editar descripcion del servicio
0? Volver
```

### Plan detail

```
*Corte Dama*
Descripcion: Corte, lavado y styling
Precio: $250.00
Estado: ? Activo
Servicio: Corte de Cabello

1? Editar nombre
2? Editar descripcion
0? Volver
```

**Scope**: No creation of services or plans from WhatsApp. No price editing.

## Profile Flow

```
*Mi Perfil*
Nombre: Carlos Admin
Email: carlos@taller.com
Telefono: +521234567890
Usuario: carlos_admin

1? Editar nombre
2? Editar email
3? Editar telefono
4? Cambiar contrasena
0? Volver
```

### Change password

```
Paso 1: ?Ingresa tu contrasena ACTUAL
Paso 2: ?Ingresa tu NUEVA contrasena (min. 8 caracteres)
Paso 3: ?Contrasena actualizada correctamente.
```

Error wrong current password: `La contrasena actual no es correcta.`

## Help Flow

```
*Ayuda - Trackpal Admin Console*

Gestiona tus clientes, catalogo y perfil desde WhatsApp.

Comandos:
- /menu - Abrir menu principal
- 0 - Volver / Cancelar / Salir

Flujos disponibles:
1? *Clientes* - Ver, crear, editar, activar/desactivar, eliminar
2? *Catalogo* - Ver servicios y planes, editar nombres y descripciones
3? *Mi Perfil* - Ver y actualizar tus datos

?Para crear clientes, desde el menu Clientes escribe +
```

## Zero Contextual Handling

| Context | "0" behavior |
|---------|-------------|
| Inside flow (editing, creating) | Cancel current operation -> previous menu |
| In list/detail view | Return to parent menu |
| In main menu | Exit session -> clear Redis -> goodbye message |

## Error Handling

All validation via centralized `validate_*()` functions. Error format:

```
{mensaje de error en espanol}
Intenta de nuevo:
```

Invalid menu option:

```
No entendi. Responde con el numero de la opcion deseada.
```

Redis failure (contingency):

```
Consola temporalmente no disponible. Intenta de nuevo en unos minutos.
```
