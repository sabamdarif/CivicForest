// Custom-design upload. The browser posts the raw image here (never to Qikink —
// credentials stay server-side); the server content-validates + re-encodes it before
// storing. The upload is multipart/form-data, so we hand a FormData body to the client.

import { apiFetch } from "./client";
import type { CustomDesignOrder } from "./types";

export interface CustomDesignInput {
  design: File;
  variant_id: string;
  print_type_id?: number;
  placement_sku?: string;
  width_inches?: number;
  height_inches?: number;
  quantity?: number;
}

export async function createCustomDesign(
  input: CustomDesignInput,
): Promise<CustomDesignOrder> {
  const form = new FormData();
  form.append("design", input.design);
  form.append("variant_id", input.variant_id);
  if (input.print_type_id != null) form.append("print_type_id", String(input.print_type_id));
  if (input.placement_sku) form.append("placement_sku", input.placement_sku);
  if (input.width_inches != null) form.append("width_inches", String(input.width_inches));
  if (input.height_inches != null) form.append("height_inches", String(input.height_inches));
  if (input.quantity != null) form.append("quantity", String(input.quantity));

  return apiFetch<CustomDesignOrder>("/custom-designs", {
    method: "POST",
    body: form,
  });
}

export async function getCustomDesigns(): Promise<CustomDesignOrder[]> {
  const data = await apiFetch<{ results: CustomDesignOrder[] }>("/custom-designs", {
    revalidate: 0,
  });
  return data.results;
}
