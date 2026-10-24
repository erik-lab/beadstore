import { api } from "./apiClient";
import type { ProductImage } from "./types";

// Matches the server's processing limit. Checked here so an oversized pick
// fails instantly rather than after a long base64 upload.
const MAX_IMAGE_BYTES = 15 * 1024 * 1024;

export const MAX_IMAGES_PER_PRODUCT = 10;

export class ImageTooLargeError extends Error {
  constructor(filename: string, bytes: number) {
    super(
      `"${filename}" is ${(bytes / 1024 / 1024).toFixed(1)}MB, over the 15MB limit. ` +
        `Most phones can export or email a smaller copy.`,
    );
  }
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result);
      const comma = result.indexOf(",");
      resolve(comma >= 0 ? result.slice(comma + 1) : result);
    };
    reader.onerror = () => reject(new Error(`Could not read "${file.name}".`));
    reader.readAsDataURL(file);
  });
}

export function listProductImages(productId: string): Promise<ProductImage[]> {
  return api.get<ProductImage[]>(`/products/${productId}/images`);
}

export async function uploadProductImage(
  productId: string,
  file: File,
  altText?: string,
): Promise<ProductImage> {
  if (file.size > MAX_IMAGE_BYTES) {
    throw new ImageTooLargeError(file.name, file.size);
  }
  return api.post<ProductImage>(`/products/${productId}/images`, {
    filename: file.name,
    data_base64: await fileToBase64(file),
    alt_text: altText ?? null,
  });
}

/** Set display order; the first id becomes the primary photo. */
export function reorderProductImages(
  productId: string,
  imageIds: string[],
): Promise<ProductImage[]> {
  return api.patch<ProductImage[]>(`/products/${productId}/images/reorder`, {
    image_ids: imageIds,
  });
}

export function updateProductImage(imageId: string, altText: string | null): Promise<ProductImage> {
  return api.patch<ProductImage>(`/products/images/${imageId}`, { alt_text: altText });
}

export function deleteProductImage(imageId: string): Promise<void> {
  return api.delete<void>(`/products/images/${imageId}`);
}
