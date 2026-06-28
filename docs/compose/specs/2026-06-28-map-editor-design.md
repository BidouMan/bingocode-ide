# Map Editor & Map Resource Manager Restoration Design

## [S1] Problem

The Vue/Tauri BingoCodeIDE has only a placeholder map editor (86 lines in `MapEditorView.vue`) — a simple PixiJS canvas with a static sidebar. The original PySide6 project has a fully-featured map editor (~3000+ lines across 12 files) with tile painting, collision editing, multi-layer support, resource management, and map library. We need to restore all of this functionality.

## [S2] Scope

Restore the following subsystems:
1. **Map Editor Main View** — 3-column layout with canvas, resource panel, and property/layer panel
2. **Map Resource Manager** — Left panel resource list, collision editor, resource import dialog
3. **Map Library Page** — Full-screen card grid for browsing/importing maps from `assets/map_lib/`
4. **Map Resource Library Page** — Full-screen card grid with 3 category tabs (images/tiles/tilesets)
5. **Map Upload Drawer** — Slide-up animated menu (import/create/open library)
6. **Map Data Model & I/O** — Binary `.info`/`.tiles`/`.collision` format, `.bgm` zip archive

## [S3] Architecture

### Components

| File | Purpose |
|------|---------|
| `MapEditorView.vue` | Main 3-column editor (rewrite from scratch) |
| `MapToolbar.vue` | Center toolbar: new/import/export/tools/grid/map-selector |
| `MapCanvas.vue` | PixiJS infinite canvas with pan/zoom, grid, tile painting |
| `ResourceListPanel.vue` | Left panel: resource list, tile grid preview, import/delete |
| `CollisionEditor.vue` | Left panel: collision shape editor for selected tile |
| `PropertyPanel.vue` | Right panel: map name, size, gravity, tile size, collision type |
| `LayerPanel.vue` | Right panel: layer list, add/delete/reorder/visibility/rename |
| `MapLibraryPage.vue` | Full-screen card grid for map library |
| `MapResourceLibPage.vue` | Full-screen card grid with 3 category tabs |
| `MapResourceImportDialog.vue` | Modal dialog for importing resources |
| `MapUploadDrawer.vue` | Slide-up animated menu (already exists, needs map-specific version) |

### Store

| File | Purpose |
|------|---------|
| `stores/map.ts` | Extend with: tool state, selected tile, layer operations, file I/O, resource management |
| `stores/resource.ts` | Already has map items — extend for map resource library |

### Data Flow

```
User clicks "New Map" → mapStore.newMap() → creates default map data → renders on canvas
User selects tile from resource panel → mapStore.selectedTile = {resourceIndex, tileIndex}
User paints on canvas → mapStore.setTile(x, y, tileId) → auto-save to .info file
User edits properties → mapStore.updateProperty() → auto-save
User imports from library → MapLibraryPage → mapStore.loadMap(path) → renders
```

## [S4] Map Editor Layout (3-Column)

```
┌─────────────────────────────────────────────────────────┐
│ Menu Bar (existing)                                     │
├───────────┬─────────────────────────┬───────────────────┤
│ LEFT 256px│ CENTER (flex)           │ RIGHT 256px       │
│           │                         │                   │
│ Resource  │ Toolbar:                │ Map Properties:   │
│ Toolbar   │ [New][Import][Export]   │ Name: ______      │
│ [Lib][Up] │ [Move][Sel][Draw][Erase]│ Size: X / Y       │
│ [Del][Clr]│ [Grid][Map Selector ▼]  │ Gravity: ☐        │
│           │                         │ Tile Size: [16▼]  │
│ Resource  │ ┌─────────────────────┐ │ Coll Type: [图像▼] │
│ List      │ │                     │ │ Tag: ______       │
│ (tileset  │ │   Map Canvas        │ │ Coll Enable: ☐    │
│  preview  │ │   (PixiJS)          │ │                   │
│  grid)    │ │                     │ │ Layer Controls:   │
│           │ │                     │ │ [Img][Tile][Del]  │
│ Collision │ │                     │ │ [Up][Down]        │
│ Toolbar   │ └─────────────────────┘ │                   │
│ [Move][+] │                         │ Layer List:       │
│ [-][Rst]  │ ┌─────────────────────┐ │ [👁 Layer 1     ] │
│ [Snap]    │ │ Map Info Bar        │ │ [👁 Layer 2     ] │
│           │ │ Name | Size | Pos   │ │                   │
│ Collision │ └─────────────────────┘ │ Layer Mode:       │
│ Editor    │                         │ drawing           │
│ (256×256) │                         │                   │
│           │                         │                   │
│ Res Info  │                         │                   │
└───────────┴─────────────────────────┴───────────────────┘
```

## [S5] Map Canvas Features

- **PixiJS 8** infinite canvas with pan (middle-click drag) and zoom (scroll wheel)
- **Grid rendering**: Dynamic grid lines at `tileSize` intervals, toggleable
- **X/Y axis lines**: Red (X) and green (Y) axis lines at origin
- **Game window indicator**: 640×480 dashed rectangle
- **Tile painting**: Click/drag to place tiles from selected resource
- **Tile erasing**: Click/drag to remove tiles
- **Tile preview**: Ghost tile follows cursor when drawing
- **Coordinate display**: Show grid position in bottom info bar
- **Zoom levels**: 0.5x to 4x, default 1.6x
- **Pan**: Middle mouse button or spacebar+drag

## [S6] Resource Panel Features

- **Resource list**: Grid of imported tileset resources (shows tile thumbnails)
- **Resource toolbar**: Open library, Upload local, Delete selected, Clear all
- **Tile preview**: When resource selected, show individual tiles in a scrollable grid
- **Tile selection**: Click tile to select for painting
- **Collision toolbar**: Move/Add/Delete anchors, Reset shape, Snap toggle
- **Collision editor**: 256×256 canvas showing collision shape for selected tile
- **Resource info**: Bottom bar showing selected resource name/size

## [S7] Property Panel Features

- **Map name**: Editable text input
- **Map size**: X/Y inputs (auto-computed from tile count)
- **Gravity**: Checkbox
- **Tile size**: Dropdown (16/32/64)
- **Collision type**: Dropdown (图像/墙体/跳板/自定义)
- **Tag**: Text input
- **Collision enable**: Checkbox

## [S8] Layer Panel Features

- **Layer list**: Scrollable list with visibility toggle and name
- **Layer controls**: Add image layer, Add drawing layer, Delete, Move up, Move down
- **Layer selection**: Click to select active layer
- **Layer rename**: Double-click to rename
- **Layer visibility**: Eye icon toggle
- **Layer mode**: Display current layer type (drawing/image)

## [S9] Map Library Page

- **Search bar**: Filter maps by name
- **Card grid**: 160×160 cards with thumbnail and name
- **Click to import**: Copies .bgm to project, loads map
- **Return button**: Go back to editor
- **Source**: `assets/map_lib/*.bgm` files

## [S10] Map Resource Library Page

- **Search bar**: Filter resources by name
- **Category tabs**: Images / Tiles / Tilesets (toggle group)
- **Card grid**: 160×160 cards with thumbnail and name
- **Click to import**: Adds resource to current map's resource list
- **Return button**: Go back to editor
- **Source**: `assets/map_res_lib/{images,tiles,tilesets}/*`

## [S11] Map Upload Drawer

- **Slide-up animation**: Green `#4B9B5C` drawer appears on hover
- **Three buttons**: Import from file, Create new map, Open map library
- **Import**: Opens file dialog for `.json` files
- **Create**: Creates new default map
- **Open library**: Navigates to map library page

## [S12] Map Data Model

### File Structure
```
assets/maps/{map_name}/
  {map_name}.info    # JSON metadata (version 5)
  {map_name}.tiles   # Binary tile data
  {map_name}.collision # Binary collision data
  {map_name}.resources # Resource paths
  tilesets/          # Copied tileset images
```

### .info Format (JSON)
```json
{
  "version": 5,
  "name": "地图1",
  "width": 40,
  "height": 30,
  "tile_size": 16,
  "offset_x": 0,
  "offset_y": 0,
  "gravity": false,
  "layers": [...],
  "tile_sets": [...],
  "layer_resources_map": {...}
}
```

### .bgm Format
- Zip archive containing all map files + `thumbnail.png`

## [S13] Styling

Match original QSS colors exactly:
- Background: `rgb(34, 37, 43)` / `#22252B`
- Editor area: `rgb(41, 44, 52)` / `#292C34`
- Canvas: `rgb(30, 30, 30)` / `#1e1e1e`
- Border: `rgb(12, 12, 12)` / `#0C0C0C`
- Hover: `rgb(61, 64, 72)` / `#3D4048`
- Active layer: `#2c313a`
- Selected: `rgb(91, 199, 114)` / `#5BC772`
- Input bg: `rgb(40, 43, 52)`
- Input border: `rgb(55, 59, 68)`
- Focus border: `#528bff`
- Label text: `#9ca0a4`
- Upload drawer: `#4B9B5C`

## [S14] Implementation Phases

### Phase 1: Core Map Editor View (MapEditorView + MapCanvas + Store)
- Rewrite `MapEditorView.vue` with 3-column layout
- Implement `MapCanvas.vue` with PixiJS pan/zoom/grid
- Extend `map.ts` store with full state management
- Basic tile painting (draw/erase tools)

### Phase 2: Resource Panel (ResourceListPanel + CollisionEditor)
- Resource list with tileset thumbnail grid
- Resource toolbar (open library, upload, delete, clear)
- Tile selection for painting
- Collision editor (basic shape display)

### Phase 3: Property & Layer Panels (PropertyPanel + LayerPanel)
- Map properties (name, size, gravity, tile size, collision type, tag)
- Layer list with visibility, rename, reorder
- Layer add/delete operations

### Phase 4: Map Toolbar & File Operations
- Map toolbar (new, import, export, tools, grid, map selector)
- Auto-save on changes
- Map file I/O (.info format)
- .bgm import/export

### Phase 5: Map Library & Resource Library Pages
- Map library page with card grid
- Map resource library page with category tabs
- Import functionality

### Phase 6: Map Upload Drawer & Integration
- Map-specific upload drawer
- Integration with MainLayout
- Full end-to-end testing

## [S15] Key Constraints

- Use **PixiJS 8** (already a dependency) for canvas rendering
- Follow existing code conventions (Composition API, Pinia stores, scoped styles)
- All icons already exist in `src/assets/icons/`
- Match original QSS colors exactly (see AGENTS.md)
- No new dependencies — use what's already in package.json
- Browser file I/O for now (Tauri native later)
- Auto-save pattern: every change triggers save

## [S16] Testing Strategy

- Manual verification: create map, paint tiles, switch layers, save/load
- Visual regression: compare layout with original PySide6 screenshots
- Functionality checklist: all 16 toolbar buttons work, all properties editable
