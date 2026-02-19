# Mutations

Mutations handle side effects: creating, updating, and deleting data. Unlike queries (which are for reading), mutations change state on the server.

## Basic Usage

```python
from pystackquery import QueryClient, MutationOptions

client = QueryClient()

async def create_user(data: dict) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.post("https://api.example.com/users", json=data) as resp:
            return await resp.json()

# Create the mutation
mutation = client.mutation(
    MutationOptions(mutation_fn=create_user)
)

# Execute it
new_user = await mutation.mutate({"name": "John", "email": "john@example.com"})
print(f"Created user: {new_user['id']}")
```

## MutationOptions Reference

```python
MutationOptions(
    mutation_fn=create_user,        # Required
    on_success=None,                # Optional
    on_error=None,                  # Optional
    on_settled=None,                # Optional
    on_mutate=None,                 # Optional
    retry=0,                        # Optional
    retry_delay=default_retry_delay,# Optional
)
```

### mutation_fn

**Type:** `Callable[[TInput], Awaitable[TData]]`

Async function that performs the mutation. Takes input data and returns the result.

```python
async def create_user(data: dict) -> dict:
    # POST to API
    return await api.post("/users", data)

async def update_user(data: dict) -> dict:
    # PUT to API
    return await api.put(f"/users/{data['id']}", data)

async def delete_user(user_id: int) -> None:
    # DELETE from API
    await api.delete(f"/users/{user_id}")
```

### on_success

**Type:** `Callable[[TData, TInput], Any] | None`

Called when mutation succeeds. Receives the result and the original input.

```python
def handle_success(result, input_data):
    print(f"Created user {result['id']} with name {input_data['name']}")

MutationOptions(
    mutation_fn=create_user,
    on_success=handle_success
)
```

Common uses:
- Show success notifications
- Invalidate related queries
- Navigate to a new page

### on_error

**Type:** `Callable[[Exception, TInput], Any] | None`

Called when mutation fails (after all retries). Receives the error and the original input.

```python
def handle_error(error, input_data):
    print(f"Failed to create user {input_data['name']}: {error}")

MutationOptions(
    mutation_fn=create_user,
    on_error=handle_error
)
```

### on_settled

**Type:** `Callable[[TData | None, Exception | None, TInput], Any] | None`

Called when mutation completes, regardless of success or failure.

```python
def handle_settled(result, error, input_data):
    if error:
        log_error(error)
    else:
        log_success(result)

MutationOptions(
    mutation_fn=create_user,
    on_settled=handle_settled
)
```

### on_mutate

**Type:** `Callable[[TInput], Awaitable[Any] | Any] | None`

Called before the mutation executes. Use for optimistic updates.

```python
def handle_mutate(input_data):
    # Optimistically update local state before the API call completes
    temp_user = {"id": "temp", **input_data}
    users_list.append(temp_user)
    return temp_user  # Return context for potential rollback

MutationOptions(
    mutation_fn=create_user,
    on_mutate=handle_mutate
)
```

### retry

**Type:** `int`
**Default:** `0`

Number of retry attempts. Default is 0 (no retries) because mutations are typically not idempotent.

```python
# No retries (default for mutations)
MutationOptions(mutation_fn=create_user, retry=0)

# Retry 3 times (for idempotent operations)
MutationOptions(mutation_fn=update_user, retry=3)
```

**Warning:** Only enable retries for idempotent mutations. Retrying a "create" operation might create duplicates.

### retry_delay

**Type:** `Callable[[int], float]`
**Default:** Exponential backoff

Same as query retry_delay. Only used if retry > 0.

## Mutation State

Access the current state of a mutation:

```python
mutation = client.mutation(MutationOptions(mutation_fn=create_user))

print(mutation.state.status)      # MutationStatus.IDLE
print(mutation.state.is_pending)  # False

await mutation.mutate(data)

print(mutation.state.status)      # MutationStatus.SUCCESS
print(mutation.state.data)        # The result
```

### MutationState Properties

| Property | Type | Description |
|----------|------|-------------|
| `status` | `MutationStatus` | Current status |
| `data` | `T \| None` | Result data (if successful) |
| `error` | `Exception \| None` | Error (if failed) |
| `submitted_at` | `float \| None` | When mutation started |
| `settled_at` | `float \| None` | When mutation completed |
| `is_idle` | `bool` | True if not yet executed |
| `is_pending` | `bool` | True if in progress |
| `is_success` | `bool` | True if succeeded |
| `is_error` | `bool` | True if failed |

### MutationStatus Enum

```python
from pystackquery import MutationStatus

MutationStatus.IDLE      # Not yet executed
MutationStatus.PENDING   # In progress
MutationStatus.SUCCESS   # Completed successfully
MutationStatus.ERROR     # Failed
```

## Subscribing to State Changes

React to mutation state changes:

```python
mutation = client.mutation(MutationOptions(mutation_fn=create_user))

def on_state_change(state):
    if state.is_pending:
        print("Processing...")
    elif state.is_success:
        print(f"Success: {state.data}")
        logging.info("Mutation completed successfully")
    elif state.is_error:
        print(f"Failed: {state.error}")
        logging.error(f"Mutation failed: {state.error}")

unsubscribe = mutation.subscribe(on_state_change)

# Execute the mutation
await mutation.mutate(data)

# When done, unsubscribe
unsubscribe()
```

## Resetting Mutation State

Reset a mutation to its initial state:

```python
mutation = client.mutation(MutationOptions(mutation_fn=create_user))

await mutation.mutate(data)
print(mutation.state.is_success)  # True

mutation.reset()
print(mutation.state.is_idle)     # True
print(mutation.state.data)        # None
```

## Invalidating Queries After Mutation

A common pattern is to invalidate related queries after a mutation:

```python
async def create_user(data: dict) -> dict:
    return await api.post("/users", data)

mutation = client.mutation(
    MutationOptions(
        mutation_fn=create_user,
        on_success=lambda result, input: asyncio.create_task(
            client.invalidate_queries(("users",))
        )
    )
)

await mutation.mutate({"name": "John"})
# The ("users",) query will be refetched
```

## Optimistic Updates

Update local state before the server responds, then rollback on error:

```python
# Store for managing optimistic state
users_cache = []

async def create_user_on_server(data: dict) -> dict:
    return await api.post("/users", data)

def on_mutate(input_data):
    # Add optimistic user
    temp_user = {"id": f"temp_{time.time()}", **input_data}
    users_cache.append(temp_user)
    return temp_user  # Save for potential rollback

def on_error(error, input_data):
    # Remove optimistic user on failure
    users_cache[:] = [u for u in users_cache if not u["id"].startswith("temp_")]

def on_success(result, input_data):
    # Replace temp user with real user
    users_cache[:] = [
        result if u["id"].startswith("temp_") else u
        for u in users_cache
    ]

mutation = client.mutation(
    MutationOptions(
        mutation_fn=create_user_on_server,
        on_mutate=on_mutate,
        on_error=on_error,
        on_success=on_success
    )
)
```

## Error Handling

Mutations raise exceptions when they fail:

```python
mutation = client.mutation(MutationOptions(mutation_fn=create_user))

try:
    result = await mutation.mutate(data)
except Exception as e:
    print(f"Mutation failed: {e}")
    # Handle error
```

If you provide `on_error`, it's called before the exception is raised.

## Multiple Mutations

Each mutation instance has its own state:

```python
create_mutation = client.mutation(MutationOptions(mutation_fn=create_user))
update_mutation = client.mutation(MutationOptions(mutation_fn=update_user))
delete_mutation = client.mutation(MutationOptions(mutation_fn=delete_user))

# Each tracks its own state independently
await create_mutation.mutate({"name": "John"})
await update_mutation.mutate({"id": 1, "name": "Jane"})
await delete_mutation.mutate(1)
```

## Type Safety

Mutations are fully typed:

```python
from pystackquery import MutationOptions

# Define types
class UserInput:
    name: str
    email: str

class User:
    id: int
    name: str
    email: str

async def create_user(data: UserInput) -> User:
    ...

# Type-safe mutation
mutation = client.mutation(
    MutationOptions[UserInput, User](mutation_fn=create_user)
)

# Type checker knows: input is UserInput, result is User
result = await mutation.mutate(UserInput(name="John", email="john@example.com"))
print(result.id)  # Type: int
```
