export interface EngineCommand {
  type: string
  id?: string
  data: Record<string, any>
}

export interface CreateCommand extends EngineCommand {
  type: 'CREATE'
  data: {
    image: string
    x: number
    y: number
    angle: number
    scale: number
    scale_x: number
    scale_y: number
    type: string
    layer: number
    vox: number
    voy: number
    raw_cw: number
    raw_ch: number
    sprite_dir?: string
    config?: any
  }
}

export interface UpdateCommand extends EngineCommand {
  type: 'UPDATE'
  data: {
    x: number
    y: number
    angle: number
    scale: number
    scale_x: number
    scale_y: number
    visible?: boolean
    layer?: number
    image?: string
    hitbox?: number[] | null
    vox: number
    voy: number
    cw: number
    ch: number
  }
}

export interface DeleteCommand extends EngineCommand {
  type: 'DELETE'
}

export interface SayCommand extends EngineCommand {
  type: 'SAY'
  data: { text: string }
}

export interface CreateBatchCommand extends EngineCommand {
  type: 'CREATE_BATCH'
  data: {
    tiles: TileData[]
    tile_sets: TileSetData[]
    tile_size: number
  }
}

export interface UpdateBatchCommand extends EngineCommand {
  type: 'UPDATE_BATCH'
  data: {
    updates: Array<{
      id: string
      x: number
      y: number
      angle: number
      scale: number
      scale_x: number
      scale_y: number
      visible?: boolean
      layer: number
      hitbox?: number[] | null
      vox: number
      voy: number
      cw: number
      ch: number
      image?: string
    }>
  }
}

export interface TileData {
  id: string
  x: number
  y: number
  type: 'tile' | 'image'
  tile_id?: number
  tile_set_index?: number
  layer: number
  tile_size: number
  angle?: number
  scale?: number
  scale_x?: number
  scale_y?: number
  opacity?: number
  image_path?: string
}

export interface TileSetData {
  name: string
  image_path: string
  image?: string
  resource_type?: string
  tile_width: number
  tile_height: number
  collision_type?: string
  collision_enabled?: boolean
  tiles?: any[]
}

export interface CameraUpdateCommand extends EngineCommand {
  type: 'CAMERA_UPDATE'
  data: {
    x: number
    y: number
    limit_left?: number
    limit_right?: number
    limit_top?: number
    limit_bottom?: number
  }
}

export interface SceneUpdateCommand extends EngineCommand {
  type: 'SCENE_UPDATE'
  data: {
    width: number
    height: number
    world_bounds: {
      left: number
      top: number
      right: number
      bottom: number
    }
  }
}

export interface PlaySoundCommand extends EngineCommand {
  type: 'PLAY_SOUND'
  data: { sound: string; loop: boolean }
}

export interface StopSoundCommand extends EngineCommand {
  type: 'STOP_SOUND'
  data: { sound?: string }
}

export interface DrawTextCommand extends EngineCommand {
  type: 'DRAW_TEXT'
  data: { id: string; text: string; x: number; y: number }
}

export interface ScreenShakeCommand extends EngineCommand {
  type: 'SCREEN_SHAKE'
  data: { intensity: number; duration: number }
}

export interface FpsUpdateCommand extends EngineCommand {
  type: 'FPS_UPDATE'
  data: { fps: number }
}

export type AnyEngineCommand =
  | CreateCommand
  | UpdateCommand
  | DeleteCommand
  | SayCommand
  | CreateBatchCommand
  | UpdateBatchCommand
  | CameraUpdateCommand
  | SceneUpdateCommand
  | PlaySoundCommand
  | StopSoundCommand
  | DrawTextCommand
  | ScreenShakeCommand
  | FpsUpdateCommand

export type InputEventType =
  | 'K_DOWN'
  | 'K_UP'
  | 'M_DOWN'
  | 'M_UP'
  | 'M_MOVE'

export interface InputEvent {
  type: InputEventType
  data: string
}
