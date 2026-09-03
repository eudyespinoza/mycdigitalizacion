# Instrucciones del repositorio

## Despliegues

- No instalar, invocar ni exigir GitHub CLI (`gh`) para este proyecto.
- El flujo aprobado desde la estación Windows es: Git HTTPS autenticado por Git Credential Manager, comprobación del workflow `CI` mediante la API REST de GitHub para el SHA exacto y actualización del VPS por SSH con el alias `mycdigitalizacion-prod`.
- Antes de actualizar el VPS, el workflow `CI` del SHA que se va a desplegar debe haber finalizado con `conclusion=success`. Un CI verde de otro commit no autoriza el despliegue.
- En el VPS, actualizar `/opt/mycdigitalizacion` únicamente mediante fast-forward, comprobar que `HEAD` coincide con el SHA aprobado, actualizar `RELEASE_ID`, validar Compose, ejecutar migraciones y verificar servicios y smoke tests.
- La receta completa y los comandos están en `docs/operations/donweb-production.md`, sección 8.
- No incluir archivos o directorios no relacionados en un commit de despliegue. En particular, `marketing/` queda fuera salvo pedido explícito del usuario.
