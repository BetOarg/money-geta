# Desktop scene visual plan

The desktop **Plan visual** tab turns an approved script's scenes into a manually reviewable storyboard of local media suggestions.

## Workflow

1. Select the existing project and campaign.
2. Click **Actualizar guiones aprobados**. Only script versions passing the current hash-bound approval check are listed.
3. Select the script and click **Generar plan de escenas**. Suggestions come from the local library; no network is used.
4. Select a scene to inspect its visual description and candidate details.
5. Choose a suggestion and click **Asignar**. **Quitar asignación** clears it. **Marcar / desmarcar revisada** records the operator's scene review.
6. Click **Guardar plan visual local** to atomically save the plan inside the campaign's `visual_plans` folder.

## Gates and behavior

- The matching engine only returns local assets marked usable after rights and integrity checks.
- An assigned asset must be among that scene's suggestions.
- Saved plans retain script ID and SHA-256, candidate metadata, selected candidate, and review state.
- A scene can be saved before every scene is reviewed, but the plan status remains `review_pending`.
- Even a fully reviewed visual plan does **not** authorize rendering or publishing. The plan always records `render_authorized=false` and `publishing_authorized=false`.
- The selected local asset can be previewed as a thumbnail (Pillow is installed through the optional `gui` extra). This tab does not download, copy, delete, render, or publish media.

Saved plan naming: `scene_asset_plan_<script-id>_<script-sha-prefix>.json`. Re-saving the same script updates that plan atomically.
