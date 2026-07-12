# Flow

State chart for the cluster dedupe/closeout workflow described in `SKILL.md`. Covers mode
selection, the autonomous-mode viability gate, the shared evidence/decision pipeline, and
the outcome states.

```mermaid
stateDiagram-v2
    [*] --> ClusterIntake

    ClusterIntake --> AutonomousViabilityGate: mode = autonomous
    ClusterIntake --> SimilaritySweep: mode = plan or execute

    state AutonomousViabilityGate {
        [*] --> FetchMain
        FetchMain --> HydrateItems
        HydrateItems --> ClassifyItems
        ClassifyItems --> IdentifyCanonicalPath
        IdentifyCanonicalPath --> [*]
    }

    AutonomousViabilityGate --> FetchEvidence: canonical path confirmed
    AutonomousViabilityGate --> ManualReviewRequired: not viable or ambiguous

    SimilaritySweep --> FetchEvidence
    FetchEvidence --> NormalizeGuardrails
    NormalizeGuardrails --> ReviewCandidateCanonicals
    ReviewCandidateCanonicals --> DecideOutcomes

    state DecideOutcomes <<choice>>
    DecideOutcomes --> KeepOpenCanonical
    DecideOutcomes --> CloseDuplicate
    DecideOutcomes --> KeepOpenRelated
    DecideOutcomes --> UnrelatedSplit
    DecideOutcomes --> ManualReviewRequired: hard-stop guardrail failed

    KeepOpenCanonical --> MergeAndChangelog: mode = execute or autonomous, PR green
    CloseDuplicate --> MergeAndChangelog: mode = execute or autonomous, PR green

    MergeAndChangelog --> EmitOutcomes
    KeepOpenRelated --> EmitOutcomes
    UnrelatedSplit --> EmitOutcomes
    ManualReviewRequired --> EmitOutcomes: plan mode drafts only

    EmitOutcomes --> [*]
```
