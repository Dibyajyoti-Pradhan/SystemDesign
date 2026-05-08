---
title: Java Collections Quick-pick
description: I need X, use Y. The decision table for the JDK collections.
---

## Pick by need

| You need… | Use | Why |
|---|---|---|
| Random-access list, append-heavy | `ArrayList` | Backing array, O(1) get, O(1)* append |
| FIFO queue / stack | `ArrayDeque` | Beats `LinkedList` and `Stack` on every metric |
| Insertion-order set | `LinkedHashSet` | Hash + doubly-linked list |
| Sorted set | `TreeSet` | Red-black tree, `headSet/tailSet/subSet` |
| Sorted map with range queries | `TreeMap` | `floorKey`, `ceilingKey`, navigable views |
| Constant-time map | `HashMap` | Default. Treeified buckets cap worst case at O(log n) |
| LRU cache | `LinkedHashMap(cap, 0.75f, true)` + override `removeEldestEntry` | `accessOrder=true` reorders on `get` |
| Identity-keyed map | `IdentityHashMap` | Uses `==` not `equals` — for object-graph traversal |
| Enum keys | `EnumMap` | Backing array indexed by ordinal, very fast |
| Enum values | `EnumSet` | Bitmask under the hood |
| Thread-safe map | `ConcurrentHashMap` | Striped locks, atomic `compute*` |
| Thread-safe sorted map | `ConcurrentSkipListMap` | Lock-free skiplist; ordered, scalable |
| Read-mostly listener list | `CopyOnWriteArrayList` | Reads lock-free; writes copy whole array |
| Producer/consumer hand-off | `LinkedBlockingQueue` (unbounded) or `ArrayBlockingQueue` (bounded) | Use bounded in production |
| Priority work queue | `PriorityBlockingQueue` | Heap-ordered, blocking |
| Delay queue (TTL events) | `DelayQueue` | Items expose `getDelay`; consumed when expired |
| Multi-value map | `Map<K, List<V>>` + `computeIfAbsent` | Or Guava `Multimap` |
| Counter map | `Map<K, Long>` + `merge(k, 1L, Long::sum)` | Idiomatic since Java 8 |
| Immutable list/set/map | `List.of`, `Set.of`, `Map.of` | Java 9+; throws on null/duplicates |
| Read-only view | `Collections.unmodifiableList(x)` | Wrapper — backing list still mutable |

## Iteration order

| Collection | Order |
|---|---|
| `ArrayList`, `LinkedList`, `ArrayDeque` | Insertion |
| `HashMap`, `HashSet` | **Undefined** — don't depend on it |
| `LinkedHashMap` / `LinkedHashSet` | Insertion (or access if `accessOrder=true`) |
| `TreeMap` / `TreeSet` | Sorted by `Comparator` / natural order |
| `EnumMap` / `EnumSet` | Enum declaration order |
| `ConcurrentHashMap` | Weakly consistent — sees a snapshot, no `CME` |
| `PriorityQueue` (iterator) | **Not** sorted — only `poll` returns in heap order |

## Common pitfalls

- `Arrays.asList(x)` returns a **fixed-size** list — `add`/`remove` throws.
- `List.of(...)` is immutable; passing it to a method that mutates blows up at runtime.
- `HashMap` performance collapses if `hashCode` is poor; `equals` and `hashCode` must agree.
- Iterating then removing → `ConcurrentModificationException`. Use `iterator.remove()` or `removeIf`.
- `Collections.synchronizedMap` locks the whole map; iteration still needs an external lock. Prefer `ConcurrentHashMap`.
- Boxed `Integer` keys: small ints (-128..127) are cached, larger ones aren't — never compare with `==`.
- `subList` returns a **view**, not a copy. Mutating the parent invalidates it.

## Quick rules

- Default to `ArrayList` and `HashMap`. Switch only with a measurement or a clear ordering need.
- Need ordering? `Linked*` for insertion, `Tree*` for sorted, never `Hash*`.
- Need concurrency? `Concurrent*` over `Collections.synchronized*` every time.
