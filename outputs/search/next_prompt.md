# Search round results

## Top candidates (by valid_rate mean)

| name | valid_rate mean |
|------|------------------|
| c9_T6_a2 | 1.0 |
| c13_T1_a2_highT | 0.966667 |
| c6_T3_a2 | 0.933333 |
| c12_T1_a2_lowT | 0.933333 |
| c5_T2_a2 | 0.9 |

## Bottom candidates

| name | valid_rate mean |
|------|------------------|
| c4_T1_a1 | 0.833333 |
| c11_T1_a2_wide_gate | 0.7 |
| c1 | 0.6 |
| c2 | 0.6 |
| c3 | 0.4 |

## Common failure signature samples

- `COMPILE:/home/aniket.salunke/fuzz4all-cs-final/outputs/search/eval_c13_T1_a2_highT/run_0/24.fuzz: In function ‘int main()’:`
- `COMPILE:/home/aniket.salunke/fuzz4all-cs-final/outputs/search/eval_c9_T6_a2/run_0/0.fuzz:N:M: warning: #pragma once in main file`
- `COMPILE:/home/aniket.salunke/fuzz4all-cs-final/outputs/search/eval_c6_T3_a2/run_0/2.fuzz:N:M: error: ‘i’ does not name a type`
- `COMPILE:/home/aniket.salunke/fuzz4all-cs-final/outputs/search/eval_c12_T1_a2_lowT/run_0/1.fuzz:N:M: error: no declaration matches ‘myClass::myClass()’`
- `COMPILE:/home/aniket.salunke/fuzz4all-cs-final/outputs/search/eval_c6_T3_a2/run_0/2_r1.fuzz:N:M: error: ‘i’ does not name a type`
- `COMPILE:/home/aniket.salunke/fuzz4all-cs-final/outputs/search/eval_c11_T1_a2_wide_gate/run_0/15_r1.fuzz: In function ‘int main()’:`
- `COMPILE:/home/aniket.salunke/fuzz4all-cs-final/outputs/search/eval_c5_T2_a2/run_0/10_r1.fuzz:N:M: error: empty character constant`
- `COMPILE:/home/aniket.salunke/fuzz4all-cs-final/outputs/search/eval_c1/run_0/9.fuzz:N:M: error: expected nested-name-specifier before ‘complex’`
- `COMPILE:/home/aniket.salunke/fuzz4all-cs-final/outputs/search/eval_c11_T1_a2_wide_gate/run_0/14_r1.fuzz: In function ‘int main()’:`
- `COMPILE:/home/aniket.salunke/fuzz4all-cs-final/outputs/search/eval_c4_T1_a1/run_0/6.fuzz:N:M: error: ‘stack’ in namespace ‘std’ does not name a template type`
- `COMPILE:/home/aniket.salunke/fuzz4all-cs-final/outputs/search/eval_c8_T5_a2/run_0/1.fuzz: In function ‘int main()’:`
- `COMPILE:/home/aniket.salunke/fuzz4all-cs-final/outputs/search/eval_c11_T1_a2_wide_gate/run_0/19_r1.fuzz: In function ‘int main()’:`
- `COMPILE:/home/aniket.salunke/fuzz4all-cs-final/outputs/search/eval_c4_T1_a1/run_0/12.fuzz: In function ‘void PopLinkedList(Node*&, int&)’:`
- `COMPILE:/home/aniket.salunke/fuzz4all-cs-final/outputs/search/eval_c8_T5_a2/run_0/5.fuzz:N:M: error: redefinition of ‘int main()’`
- `COMPILE:/home/aniket.salunke/fuzz4all-cs-final/outputs/search/eval_c11_T1_a2_wide_gate/run_0/8.fuzz: In function ‘int main()’:`

---

Please propose the next round of candidate configs in the same JSON format.
Format: a JSON array of objects with "name", "gen", and "repair" keys.
"gen" can override llm/fuzzing; "repair" can override repair section.
Save as candidates/round_03.json.
