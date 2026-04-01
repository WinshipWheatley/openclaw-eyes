title: mus-012-album-production-matrix
profile: standard
goal: Build a 12-song completion matrix from local project directories, flagging tracks as Mastered vs In Progress from file-state evidence.
scope:
- Scan configured local music project directories for assets tied to the 12-song project.
- Detect state signals from file names, stems, render outputs, and last-modified timestamps.
- Label each track as Mastered, In Progress, or Unknown with supporting evidence.
- Produce a matrix report with track name, status, last modified date, and evidence path.
- Save matrix to vault path under Album or System reporting docs.
success:
- Matrix includes all 12 songs with status and evidence references.
- Unknown entries are explicitly listed with next-step suggestions.
verification: |
  python3 -c "print('mus-012-matrix-spec-ready')"
