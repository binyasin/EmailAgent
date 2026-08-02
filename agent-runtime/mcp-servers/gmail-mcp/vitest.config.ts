import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    env: {
      CONTROL_PLANE_INTERNAL_URL: "http://control-plane.test",
      CELL_SERVICE_TOKEN: "test-cell-service-token",
    },
  },
});
