# PRISMA Flow Diagram

```mermaid
flowchart TD
  A["Records identified from database searches: 324"]
  B["Records after duplicate removal: 223"]
  C["Records screened by title/abstract: 319"]
  D["Records excluded: 0"]
  E["Full-text records assessed: 319"]
  F["Full-text records excluded: 0"]
  G["Studies included in SOTA synthesis: 319"]
  H["Studies included in DuE/equivalence evidence: 0"]
  A --> B --> C
  C --> D
  C --> E
  E --> F
  E --> G
  E --> H
```

Note: this diagram is generated from the reproducible search and screening registry; final PRISMA reporting requires human confirmation of exclusions and full-text decisions.
