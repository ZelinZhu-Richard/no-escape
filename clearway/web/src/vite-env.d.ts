/// <reference types="vite/client" />
interface Window {
  CESIUM_BASE_URL?: string;
  __clearwayMapMetrics?: {
    viewer_initializations: number;
    tileset_initializations: number;
    root_tile_requests: number;
    tile_content_requests: number;
  };
}
