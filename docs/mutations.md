# Mutations

Mutations are for side effects: creating, updating, or deleting data. While Queries are for "Read" operations, Mutations handle the "Write" operations.

## Usage

```python
from pystackquery import QueryClient, MutationOptions

client = QueryClient()

async def create_user(data):
    # Perform your POST request here
    return {"id": "1", **data}

# 1. Initialize
mutation = client.mutation(MutationOptions(mutation_fn=create_user))

# 2. Execute
result = await mutation.mutate({"name": "John"})
```

## Optimistic Updates

PyStackQuery supports updating the cache **before** the server responds. If the server fails, you can rollback.

```python
def on_mutate(variables):
    # Update cache immediately for instant UI response
    client.set_query_data(("users",), lambda old: [*old, variables])
    return {"old_data": old} # Rollback context

mutation = client.mutation(MutationOptions(
    mutation_fn=create_user,
    on_mutate=on_mutate,
    on_error=lambda err, vars, ctx: client.set_query_data(("users",), ctx["old_data"])
))
```

## Reactive Mutation State

Mutations also support observers. You can subscribe to a mutation to track its status (PENDING, SUCCESS, ERROR) across your application.

```python
mutation = client.mutation(MutationOptions(mutation_fn=create_user))

# Subscribing is synchronous
unsubscribe = mutation.subscribe(lambda state: print(f"Status: {state.status}"))

await mutation.mutate({"name": "Jane"})
```

## Lifecycle Callbacks

*   **on_mutate:** Called before `mutation_fn`. Used for optimistic updates.
*   **on_success:** Called on successful completion.
*   **on_error:** Called if the mutation fails (after retries).
*   **on_settled:** Called regardless of outcome.
