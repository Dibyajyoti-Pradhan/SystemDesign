---
title: Big-O Cheat Sheet
description: Java collections complexity, the cases that bite, and the constants that actually matter.
---

## Core JDK structures

| Structure | add | remove | get / contains | Notes |
|---|---|---|---|---|
| `ArrayList` | O(1)* / O(n) at index | O(n) | O(1) get / O(n) contains | `*` amortised on append; `add(0, x)` shifts all elements |
| `LinkedList` | O(1) at ends | O(1) at ends, O(n) at index | O(n) get / O(n) contains | Iterator-based ops are O(1); rarely the right pick |
| `ArrayDeque` | O(1) amortised | O(1) at ends | O(n) contains | Beats `LinkedList` and `Stack` for queue/stack |
| `HashMap` / `HashSet` | O(1) avg, O(log n) worst | O(1) avg | O(1) avg | Treeified bucket since Java 8 (≥8 entries hash-colliding) |
| `LinkedHashMap` | O(1) | O(1) | O(1) | Iteration order = insertion (or access if `accessOrder=true`) |
| `TreeMap` / `TreeSet` | O(log n) | O(log n) | O(log n) | Red-black tree; sorted; `firstKey/lastKey` are O(log n) |
| `PriorityQueue` | O(log n) | O(log n) `poll`, O(n) `remove(obj)` | O(1) `peek` / O(n) `contains` | Binary min-heap; not thread-safe |
| `ConcurrentHashMap` | O(1) avg | O(1) avg | O(1) avg | Striped locks since Java 8; `size()` is approximate |
| `CopyOnWriteArrayList` | O(n) | O(n) | O(1) get | Reads lock-free; great for read-mostly listener lists |

## Sort, search, scan

| Operation | Cost |
|---|---|
| `Collections.sort` / `Arrays.sort` (Object) | O(n log n) — Timsort, stable |
| `Arrays.sort` (primitive) | O(n log n) — Dual-pivot Quicksort, **not** stable |
| `Arrays.binarySearch` | O(log n) on sorted array |
| `String.contains` / `indexOf` | O(n·m) worst, O(n+m) typical |
| `stream().collect(toList())` | O(n) + allocation; lambda dispatch isn't free |

## Pitfalls that cost interviews

- `ArrayList.remove(0)` is O(n). Use `ArrayDeque` for FIFO.
- `LinkedList.get(i)` is O(n). It is *not* the random-access list.
- `HashMap` worst case is O(log n) only when keys implement `Comparable`; otherwise it's O(n).
- `PriorityQueue.remove(Object)` is O(n) — heap property doesn't help arbitrary deletion. Use a `TreeSet` if you need both ordering and arbitrary delete.
- `Stream.parallel()` on a `LinkedList` is slower than sequential — bad spliterator.
- `String + String` in a loop is O(n²). Use `StringBuilder`.
- `Set.contains` on `TreeSet` is O(log n), not O(1). Reach for `HashSet` unless you need order.
- `Map.keySet().contains(k)` allocates nothing, but `new ArrayList<>(map.keySet()).contains(k)` does.

## Memory rules of thumb

- Object header: 12–16 bytes. A `HashMap.Node` is ~48 bytes — huge maps dominate heap.
- `ArrayList` grows by 1.5×; `HashMap` doubles at load factor 0.75.
- Pre-size when you know N: `new HashMap<>(expected * 4 / 3 + 1)`.
