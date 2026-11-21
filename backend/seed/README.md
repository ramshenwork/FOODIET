# Reference seed data

**Placeholder values. Not for publication.** Every nutrient value here is an approximate generic figure
entered by the builder so the engine can be developed and tested. None of it is copied from IFCT, INDB
or any other licensed source. Every profile is seeded with `source = "placeholder"` and
`licence_status = "pending"`, so the engine refuses to use it for a published calculation
(`require_cleared=True`) until a nutrition professional replaces it with licensed data and an admin clears it.

Reference recipes carry `"reviewed": false` until a nutrition professional has checked them.
The ten benchmark recipes in the engine tests are drawn from this file.

Files:
- `ingredients.json`: per-100 g values; `null` means unknown and stays unknown in every result.
- `canonical_dishes.json`: names, aliases, and the expected kcal per 100 g range used by plausibility checks.
- `reference_recipes.json`: platform recipes behind the Estimated label. Ingredients are referenced by name;
  `"sub": "<reference name>"` uses another reference recipe as a sub-recipe.

Load with: `cd backend && ../.venv/bin/python -m jobs.seed_reference`
