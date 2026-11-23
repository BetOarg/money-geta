# Auditoría de capacidades de perfiles

## Uso
Ejecutar desde la raíz del repositorio:

```powershell
python -m scripts.money_geta profiles audit
```

Este comando es una auditoría declarativa, de solo lectura. Lista cada capacidad declarada, la clasifica como `available`, `partial`, `planned` o `unknown`, y muestra gaps. Un perfil solo puede aparecer como `ready` si su declaración es `ready` y todas sus capacidades están `available`; la implementación actual no marca capacidades como `available`, por lo que no puede certificar perfiles listos.

## Criterios conservadores

- `partial`: existe implementación o adaptador, pero no está verificado end-to-end para todos los perfiles/escenarios.
- `planned`: la capacidad está en la lista declarada pero todavía no hay una base implementada que permita considerarla.
- `unknown`: capacidad no reconocida en el inventario del auditor; se reporta como gap y nunca se presume soportada.
- GTA VI `moment-detection` y `clip-editing` quedan limitados a ese subperfil de Gaming. El auditor no declara que estos módulos funcionen para Minecraft, Fortnite, Roblox u otros juegos.

El inventario de capacidad es intencionalmente conservador y debe actualizarse junto con pruebas/evidencia de implementación. El reporte no sustituye pruebas locales, verificación factual, derechos, QC ni aprobación humana.
