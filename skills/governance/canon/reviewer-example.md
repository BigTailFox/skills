# Machine reviewer file

Fill these placeholders in the machine-local reviewer file. Use the user's actual priorities. Keep a grant unfilled until the user explicitly accepts its scope. An example or file copy authorizes no transmission.

## Reviewer priorities

### `<initiating family>`

- `<host>` — [Primary reviewer](#primary-reviewer), [Alternate reviewer](#alternate-reviewer)

### Default

- `<host or all hosts>` — [Alternate reviewer](#alternate-reviewer)

Use `none` for a family or host where the user wants manual review.

## Reviewer definitions

### Primary reviewer

- Family `<family>`, model `<model>`, effort `<effort>`.
- Hosts `<supported hosts>`. Prerequisites `<local conditions and login>`.
- Run the [shared launcher](#shared-launcher) with this model and effort at `<destination>`, with `<input limits and allowed read-only tools>`.

**Transmission grant (unfilled)**

| Field | Fill from the user's decision |
|---|---|
| Decision and source | `<what the user authorized and where>` |
| Destination and model | `<provider destination and model>` |
| Allowed tools | `<read-only tools>` |
| Repository identities | `<canonical absolute Git common directories or non-Git project roots>` |
| Permitted inputs | `<prompt, files or diffs and path limits>` |
| Phases and calls | `<authorized setup trial, design, plan, code review, confirmation or recovery calls>` |
| Lifetime | `<named batch, or standing with chosen expiry or until revoked>` |

### Alternate reviewer

- Family `<family>`, model `<model>`, effort `<effort>`.
- Hosts `<supported hosts>`. Prerequisites `<local conditions and login>`.
- Run the [shared launcher](#shared-launcher) with this model and effort at `<destination>`, with `<input limits and allowed read-only tools>`.

**Transmission grant (unfilled)**

`<fill the same seven fields here from a user decision covering this route>`

### Shared launcher

| Operation | Machine-local configuration |
|---|---|
| Fresh read-only session | `<local command using the definition's destination, model, effort and confined inputs>` with `<prompt>` and `<out>` |
| Display and ID | `<where observed events are flushed and how the opening ID is bound to the output>` |
| Read-only status | `<local operation for the retained job>` |
| Recovery | `<demonstrated operation for the bound session and output, and its limit, if supported>` |

Keep credentials in the provider's local credential store. Describe only capabilities verified in setup.
