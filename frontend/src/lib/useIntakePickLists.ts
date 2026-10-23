import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./apiClient";
import type { Location, ProductCategory, ProductSubtype, Vendor } from "./types";

/**
 * The existing names an import review offers in its dropdowns.
 *
 * Loaded once for the whole batch and passed down to every row — a 200-row
 * review would otherwise fire the same handful of requests 200 times over.
 *
 * Subtypes and attribute options are fetched on demand: subtypes are scoped
 * to a category, and attribute pick lists are fifteen separate endpoints that
 * are only worth hitting once a reviewer actually opens a row's details.
 * Both are cached for the life of the page.
 */
export interface IntakePickLists {
  categories: string[];
  vendors: string[];
  locations: string[];
  /** Subtype names for a category name — [] until loaded. */
  subtypesFor: (categoryName: string) => string[];
  /** Pick-list values for a product attribute field — [] until loaded. */
  attributeOptionsFor: (field: string) => string[];
  /** Pull in a newly created name so the dropdowns don't go stale. */
  reload: () => void;
}

export function useIntakePickLists(): IntakePickLists {
  const [categories, setCategories] = useState<ProductCategory[]>([]);
  const [vendors, setVendors] = useState<string[]>([]);
  const [locations, setLocations] = useState<string[]>([]);
  const [subtypes, setSubtypes] = useState<Record<string, string[]>>({});
  const [attributeOptions, setAttributeOptions] = useState<Record<string, string[]>>({});
  const [version, setVersion] = useState(0);

  // Tracks what's already been requested so a render loop can't re-fire the
  // same lazy fetch — these are read during render, not in an effect.
  const requested = useRef<Set<string>>(new Set());

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      api.get<ProductCategory[]>("/product-categories"),
      api.get<Vendor[]>("/vendors?limit=200"),
      api.get<Location[]>("/locations"),
    ])
      .then(([categoryRows, vendorRows, locationRows]) => {
        if (cancelled) return;
        setCategories(categoryRows);
        setVendors(vendorRows.map((v) => v.name).sort((a, b) => a.localeCompare(b)));
        setLocations(locationRows.map((l) => l.name).sort((a, b) => a.localeCompare(b)));
      })
      .catch(() => {
        // A failed pick list isn't fatal: the dropdowns fall back to whatever
        // the import already holds, and the row's own value is still kept.
      });
    return () => {
      cancelled = true;
    };
  }, [version]);

  const subtypesFor = useCallback(
    (categoryName: string): string[] => {
      if (!categoryName) return [];
      const key = categoryName.toLowerCase();
      if (key in subtypes) return subtypes[key];

      // A category that isn't on file yet has no subtypes to fetch. Nothing
      // is recorded for it, so it resolves on its own once the category is
      // created and the pick lists reload.
      const category = categories.find((c) => c.name.toLowerCase() === key);
      if (!category) return [];

      if (!requested.current.has(`sub:${key}`)) {
        requested.current.add(`sub:${key}`);
        api
          .get<ProductSubtype[]>(`/product-categories/${category.id}/subtypes`)
          .then((rows) =>
            setSubtypes((prev) => ({
              ...prev,
              [key]: rows.map((r) => r.name).sort((a, b) => a.localeCompare(b)),
            })),
          )
          .catch(() => setSubtypes((prev) => ({ ...prev, [key]: [] })));
      }
      return [];
    },
    [categories, subtypes],
  );

  const attributeOptionsFor = useCallback(
    (field: string): string[] => {
      if (field in attributeOptions) return attributeOptions[field];
      if (!requested.current.has(`attr:${field}`)) {
        requested.current.add(`attr:${field}`);
        api
          .get<string[]>(`/products/attribute-options?field=${encodeURIComponent(field)}`)
          .then((values) => setAttributeOptions((prev) => ({ ...prev, [field]: values })))
          .catch(() => setAttributeOptions((prev) => ({ ...prev, [field]: [] })));
      }
      return [];
    },
    [attributeOptions],
  );

  const reload = useCallback(() => {
    requested.current = new Set();
    setSubtypes({});
    setAttributeOptions({});
    setVersion((v) => v + 1);
  }, []);

  return {
    categories: categories.map((c) => c.name).sort((a, b) => a.localeCompare(b)),
    vendors,
    locations,
    subtypesFor,
    attributeOptionsFor,
    reload,
  };
}
