# SISDAS RAG Assistant Design Direction

## Identity

SISDAS RAG Assistant is a calm academic utility for students and campus staff who need answers from official Universitas Negeri Malang documents.

## Audience

- Students checking academic, finance, scholarship, facility, and graduation information.
- Campus staff or reviewers validating that answers are grounded in source documents.

## Visual Thesis

Quiet academic workspace: light surfaces, deep institutional green, compact hierarchy, and evidence-first content.

## Dials

ENERGY 1 / RHYTHM 1 / MOTION 1

## Palette

- Base: soft green-white background for a campus document workspace.
- Primary: deep green for navigation, action, status, and active state.
- Accent: pale mint for secondary labels and source metadata.
- Destructive: restrained red only for errors.

## Typography

Use the system sans stack for speed, readability, and native UI familiarity. Avoid decorative display type and large monospace styling because the product is an academic assistant, not a terminal tool.

## Layout

The app starts from the user task: ask, read the answer, verify the source. Navigation stays compact, content width stays readable, and result states should make the answer and evidence more important than the initial prompt.

## Components

Use cards only when grouping a meaningful artifact, such as a generated answer, process summary, document domain, or source excerpt. Routine supporting content should prefer plain layout, dividers, compact rows, or subtle bordered groups.

## Motion

Motion is limited to direct feedback: loading spinner, hover, focus, and short state transitions. Stable statuses should not loop endlessly.
