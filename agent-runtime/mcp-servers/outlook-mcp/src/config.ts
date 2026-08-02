function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Missing required env var ${name}`);
  }
  return value;
}

export const config = {
  controlPlaneInternalUrl: requireEnv("CONTROL_PLANE_INTERNAL_URL"),
  // A per-org JWT minted at cell-provisioning time (see
  // control-plane/app/core/security.py's create_cell_service_token) — org
  // identity is derived from this token server-side, not from a
  // client-supplied tenant id, so there's no TENANT_ID here to trust for
  // authorization purposes (kept as an optional env var elsewhere only for
  // human-readable logging, if set at all).
  cellServiceToken: requireEnv("CELL_SERVICE_TOKEN"),
};
