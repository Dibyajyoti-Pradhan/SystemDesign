# Core Java Interview Preparation

**Checklist format — work through sections top-to-bottom. Each section builds on the previous.**

> Topics marked `- [ ]` can be checked off as `- [x]` when studied.

---

## Section 1 — JVM Internals & Platform Foundations

| # | Topic | Studied |
|---|-------|---------|
| 1.01 | [JDK vs JRE vs JVM — roles and differences](Java/01%20-%20JDK%20vs%20JRE%20vs%20JVM.pdf) | - [ ] |
| 1.02 | [ClassLoader subsystem — Bootstrap, Extension, Application](Java/02%20-%20ClassLoader%20Subsystem.pdf) | - [ ] |
| 1.03 | [Class loading phases — Loading, Linking (Verify/Prepare/Resolve), Initializing](Java/03%20-%20Class%20Loading%20Phases.pdf) | - [ ] |
| 1.04 | [JIT Compiler — interpreted vs compiled execution, tiered compilation](Java/04%20-%20JIT%20Compiler.pdf) | - [ ] |
| 1.05 | [JVM Memory Layout — Heap, Stack, Method Area, PC Register, Native Stack](Java/05%20-%20JVM%20Memory%20Layout.pdf) | - [ ] |
| 1.06 | Stack frames — local variables, operand stack, return address | - [ ] |
| 1.07 | How Java achieves platform independence (bytecode + JVM contract) | - [ ] |

---

## Section 2 — Language Basics & Types

| # | Topic | Studied |
|---|-------|---------|
| 2.01 | Primitive types — sizes, ranges, default values | - [ ] |
| 2.02 | Wrapper classes & Autoboxing / Unboxing — caching range (-128 to 127) | - [ ] |
| 2.03 | Type casting — widening vs narrowing, truncation risks | - [ ] |
| 2.04 | Operators — bitwise, shift, ternary, instanceof | - [ ] |
| 2.05 | String class — immutability, String Pool, `intern()` | - [ ] |
| 2.06 | StringBuilder vs StringBuffer — thread-safety, performance | - [ ] |
| 2.07 | String comparison — `==` vs `.equals()` vs `.compareTo()` | - [ ] |
| 2.08 | Arrays — single/multi-dimensional, System.arraycopy, Arrays utility class | - [ ] |
| 2.09 | Varargs — declaration rules, interaction with overloading | - [ ] |
| 2.10 | Pass-by-value vs pass-by-reference in Java (always pass-by-value) | - [ ] |

---

## Section 3 — Object-Oriented Programming

| # | Topic | Studied |
|---|-------|---------|
| 3.01 | Classes & Objects — `new`, constructors, default constructor | - [ ] |
| 3.02 | Constructor chaining — `this()`, `super()`, ordering rules | - [ ] |
| 3.03 | Initialization order — static blocks, instance blocks, constructors | - [ ] |
| 3.04 | Encapsulation — access modifiers (private/default/protected/public) | - [ ] |
| 3.05 | Inheritance — `extends`, single inheritance, constructor propagation | - [ ] |
| 3.06 | Method overriding — covariant return types, `@Override`, rules | - [ ] |
| 3.07 | Polymorphism — compile-time (overloading) vs runtime (overriding) | - [ ] |
| 3.08 | Abstract classes — abstract methods, partial implementation | - [ ] |
| 3.09 | Interfaces — contract definition, default methods, static methods | - [ ] |
| 3.10 | Abstract class vs Interface — when to use which | - [ ] |
| 3.11 | `final` keyword — final class, final method, final variable (blank final) | - [ ] |
| 3.12 | `static` keyword — static methods, static fields, static blocks | - [ ] |
| 3.13 | `this` and `super` — reference semantics in constructors vs methods | - [ ] |
| 3.14 | Object class methods — `equals()`, `hashCode()`, `toString()`, `clone()` | - [ ] |
| 3.15 | `equals` & `hashCode` contract — why they must be overridden together | - [ ] |
| 3.16 | Immutable classes — design pattern, `final` fields, defensive copying | - [ ] |
| 3.17 | Nested classes — Static nested, Inner, Local, Anonymous — use cases | - [ ] |
| 3.18 | Enums — constructor, methods, `ordinal()`, `values()`, use in switch | - [ ] |

---

## Section 4 — Generics

| # | Topic | Studied |
|---|-------|---------|
| 4.01 | Generic classes and methods — syntax, type parameters | - [ ] |
| 4.02 | Bounded type parameters — `<T extends Comparable<T>>` | - [ ] |
| 4.03 | Wildcards — unbounded `<?>`, upper `<? extends T>`, lower `<? super T>` | - [ ] |
| 4.04 | PECS principle — Producer Extends, Consumer Super | - [ ] |
| 4.05 | Type erasure — what gets erased, raw types, bridge methods | - [ ] |
| 4.06 | Generic restrictions — cannot instantiate `T`, no generic arrays | - [ ] |
| 4.07 | Comparable vs Comparator — natural order vs custom order | - [ ] |

---

## Section 5 — Exception Handling

| # | Topic | Studied |
|---|-------|---------|
| 5.01 | Exception hierarchy — Throwable → Error / Exception → RuntimeException | - [ ] |
| 5.02 | Checked vs Unchecked exceptions — compile-time enforcement | - [ ] |
| 5.03 | `try-catch-finally` — execution order, finally always runs | - [ ] |
| 5.04 | `try-with-resources` — AutoCloseable, suppressed exceptions | - [ ] |
| 5.05 | Multi-catch — `catch (A | B e)` — restrictions | - [ ] |
| 5.06 | Exception chaining — `initCause()`, cause propagation | - [ ] |
| 5.07 | Custom exceptions — checked vs unchecked choice, best practices | - [ ] |
| 5.08 | Common interview traps — return in finally, re-throwing, swallowing | - [ ] |

---

## Section 6 — Collections Framework

| # | Topic | Studied |
|---|-------|---------|
| 6.01 | Collection hierarchy — Iterable → Collection → List / Set / Queue / Deque | - [ ] |
| 6.02 | ArrayList — backing array, resizing (1.5×), index-based access O(1) | - [ ] |
| 6.03 | LinkedList — doubly-linked, Deque interface, O(n) random access | - [ ] |
| 6.04 | ArrayList vs LinkedList — when to use each | - [ ] |
| 6.05 | HashMap internals — hashing, buckets, load factor (0.75), rehashing | - [ ] |
| 6.06 | HashMap collision handling — chaining, Java 8 treeify at bucket size 8 | - [ ] |
| 6.07 | LinkedHashMap — insertion/access order, LRU cache use case | - [ ] |
| 6.08 | TreeMap — Red-Black tree, O(log n) operations, NavigableMap | - [ ] |
| 6.09 | HashSet / LinkedHashSet / TreeSet — backed by corresponding Map | - [ ] |
| 6.10 | PriorityQueue — min-heap, O(log n) offer/poll, O(1) peek | - [ ] |
| 6.11 | ArrayDeque — stack and queue operations, preferred over Stack class | - [ ] |
| 6.12 | Fail-fast vs Fail-safe iterators — ConcurrentModificationException | - [ ] |
| 6.13 | Collections utility class — sort, binarySearch, unmodifiableList, synchronizedList | - [ ] |
| 6.14 | Choosing the right collection — cheat sheet for interviews | - [ ] |

---

## Section 7 — Memory Management & Garbage Collection

| # | Topic | Studied |
|---|-------|---------|
| 7.01 | Heap regions — Young Gen (Eden + S0/S1), Old Gen, Metaspace | - [ ] |
| 7.02 | Minor GC vs Major GC vs Full GC | - [ ] |
| 7.03 | GC algorithms — Serial, Parallel, CMS (deprecated), G1, ZGC, Shenandoah | - [ ] |
| 7.04 | G1GC — region-based, mixed collections, pause targets | - [ ] |
| 7.05 | Reference types — Strong, Soft, Weak, Phantom | - [ ] |
| 7.06 | Memory leaks in Java — common causes (static collections, listeners, ThreadLocal) | - [ ] |
| 7.07 | OutOfMemoryError types — Heap space, Metaspace, StackOverflow | - [ ] |
| 7.08 | `finalize()` — why it's deprecated, alternatives (Cleaner, try-with-resources) | - [ ] |

---

## Section 8 — Multithreading & Concurrency

| # | Topic | Studied |
|---|-------|---------|
| 8.01 | Thread vs Process — memory sharing, context switching | - [ ] |
| 8.02 | Thread lifecycle — NEW, RUNNABLE, BLOCKED, WAITING, TIMED_WAITING, TERMINATED | - [ ] |
| 8.03 | Creating threads — `Thread` subclass vs `Runnable` vs `Callable` | - [ ] |
| 8.04 | `synchronized` keyword — instance vs class-level locking | - [ ] |
| 8.05 | `volatile` keyword — visibility guarantee, no atomicity | - [ ] |
| 8.06 | Java Memory Model — happens-before, instruction reordering | - [ ] |
| 8.07 | `wait()`, `notify()`, `notifyAll()` — must be called inside synchronized block | - [ ] |
| 8.08 | Race conditions — check-then-act, read-modify-write patterns | - [ ] |
| 8.09 | Deadlock — conditions (MHCW), detection, prevention strategies | - [ ] |
| 8.10 | Livelock & Starvation — definitions, causes, mitigations | - [ ] |
| 8.11 | `Executor` framework — Executor, ExecutorService, ScheduledExecutorService | - [ ] |
| 8.12 | Thread pools — Fixed, Cached, Single, Scheduled, Work-Stealing (ForkJoin) | - [ ] |
| 8.13 | `Future` & `Callable` — submitting tasks, `get()`, cancellation | - [ ] |
| 8.14 | `CompletableFuture` — `thenApply`, `thenCompose`, `allOf`, `anyOf`, error handling | - [ ] |
| 8.15 | `ReentrantLock` — fairness, `tryLock()`, interruptible lock | - [ ] |
| 8.16 | `ReadWriteLock` — concurrent reads, exclusive writes | - [ ] |
| 8.17 | Atomic classes — `AtomicInteger`, `AtomicReference`, CAS operations | - [ ] |
| 8.18 | `CountDownLatch` — one-time gate, await until count reaches zero | - [ ] |
| 8.19 | `CyclicBarrier` — reusable, all parties wait at barrier | - [ ] |
| 8.20 | `Semaphore` — controlling access to a pool of resources | - [ ] |
| 8.21 | `ConcurrentHashMap` — segment locking (Java 7) vs CAS + synchronized (Java 8) | - [ ] |
| 8.22 | `CopyOnWriteArrayList` — read-heavy use cases, snapshot iterator | - [ ] |
| 8.23 | `BlockingQueue` — `LinkedBlockingQueue`, `ArrayBlockingQueue`, producer-consumer | - [ ] |
| 8.24 | ThreadLocal — per-thread storage, memory leak risk in thread pools | - [ ] |

---

## Section 9 — Functional Programming & Java 8

| # | Topic | Studied |
|---|-------|---------|
| 9.01 | Lambda expressions — syntax, effectively final variables | - [ ] |
| 9.02 | Functional interfaces — `@FunctionalInterface`, single abstract method | - [ ] |
| 9.03 | Built-in functional interfaces — `Predicate`, `Function`, `Consumer`, `Supplier`, `BiFunction` | - [ ] |
| 9.04 | Method references — static, instance (bound/unbound), constructor | - [ ] |
| 9.05 | Streams API — `stream()`, `parallelStream()`, lazy evaluation | - [ ] |
| 9.06 | Intermediate operations — `map`, `filter`, `flatMap`, `distinct`, `sorted`, `peek` | - [ ] |
| 9.07 | Terminal operations — `collect`, `forEach`, `reduce`, `count`, `findFirst`, `anyMatch` | - [ ] |
| 9.08 | Collectors — `toList`, `toMap`, `groupingBy`, `joining`, `partitioningBy` | - [ ] |
| 9.09 | `Optional` — `of`, `ofNullable`, `map`, `flatMap`, `orElse`, `orElseThrow` | - [ ] |
| 9.10 | `Optional` misuse — not a replacement for null checks in fields | - [ ] |
| 9.11 | Default & static methods in interfaces — backwards compatibility design | - [ ] |
| 9.12 | Date/Time API — `LocalDate`, `LocalDateTime`, `ZonedDateTime`, `Duration`, `Period` | - [ ] |

---

## Section 10 — Modern Java (Java 9–21)

| # | Topic | Studied |
|---|-------|---------|
| 10.01 | Java 9 — Module system (JPMS), `module-info.java`, `requires`/`exports` | - [ ] |
| 10.02 | Java 10 — `var` (local variable type inference), scope rules | - [ ] |
| 10.03 | Java 11 — `String` methods (`isBlank`, `strip`, `lines`, `repeat`), `var` in lambdas | - [ ] |
| 10.04 | Java 14 — Records — immutable data carriers, auto-generated accessors/equals/hashCode | - [ ] |
| 10.05 | Java 15 — Sealed classes — restrict subclassing hierarchy | - [ ] |
| 10.06 | Java 16 — Pattern matching for `instanceof` — eliminates cast | - [ ] |
| 10.07 | Java 17 — Text blocks — multiline string literals, indentation trimming | - [ ] |
| 10.08 | Java 21 — Virtual threads (Project Loom) — lightweight concurrency, structured concurrency | - [ ] |
| 10.09 | Java 21 — Pattern matching for `switch` — guards, completeness | - [ ] |
| 10.10 | Java 21 — Sequenced collections — `SequencedCollection`, `SequencedMap` | - [ ] |

---

## Section 11 — I/O, Serialization & NIO

| # | Topic | Studied |
|---|-------|---------|
| 11.01 | `java.io` — byte streams (InputStream/OutputStream) vs character streams (Reader/Writer) | - [ ] |
| 11.02 | `File` vs `Path`/`Files` (NIO.2) — preferred modern API | - [ ] |
| 11.03 | Buffered I/O — `BufferedReader`, `BufferedWriter` — why buffering matters | - [ ] |
| 11.04 | Serialization — `Serializable`, `serialVersionUID`, object graph | - [ ] |
| 11.05 | `transient` keyword — excluding fields from serialization | - [ ] |
| 11.06 | `Externalizable` — custom serialization logic | - [ ] |
| 11.07 | Java NIO — Channels, Buffers, Selectors, non-blocking I/O | - [ ] |
| 11.08 | Memory-mapped files — `MappedByteBuffer`, zero-copy reads | - [ ] |

---

## Section 12 — Design Patterns in Java Context

| # | Topic | Studied |
|---|-------|---------|
| 12.01 | Singleton — eager, lazy, double-checked locking, `volatile`, enum singleton | - [ ] |
| 12.02 | Factory Method & Abstract Factory — decoupling object creation | - [ ] |
| 12.03 | Builder — telescoping constructors problem, fluent API, immutable objects | - [ ] |
| 12.04 | Prototype — `clone()`, shallow vs deep copy | - [ ] |
| 12.05 | Decorator — wrapping via composition, `java.io` streams example | - [ ] |
| 12.06 | Proxy — static vs dynamic proxy (`java.lang.reflect.Proxy`) | - [ ] |
| 12.07 | Observer — `EventListener`, publish-subscribe, avoiding memory leaks | - [ ] |
| 12.08 | Strategy — injecting algorithms, replacing conditionals | - [ ] |
| 12.09 | Template Method — abstract skeleton, Hollywood principle | - [ ] |
| 12.10 | Dependency Injection — constructor vs setter vs field injection | - [ ] |
| 12.11 | SOLID Principles — with Java code examples for each | - [ ] |

---

## Section 13 — Java Performance & Best Practices

| # | Topic | Studied |
|---|-------|---------|
| 13.01 | String interning — when to use, performance tradeoffs | - [ ] |
| 13.02 | Object pooling — connection pools, `Flyweight` pattern | - [ ] |
| 13.03 | Avoiding unnecessary boxing/unboxing in loops | - [ ] |
| 13.04 | Profiling — JVisualVM, JProfiler, async-profiler basics | - [ ] |
| 13.05 | Benchmarking with JMH — avoiding JIT warmup pitfalls | - [ ] |
| 13.06 | Common anti-patterns — catching Throwable/Exception, empty catch blocks, overusing static | - [ ] |
| 13.07 | Effective Java principles — key items for interviews (Item 1, 17, 28, 50, 78…) | - [ ] |

---

## Quick Reference: Interview Complexity Cheat Sheet

| Operation | ArrayList | LinkedList | HashMap | TreeMap | HashSet | PriorityQueue |
|-----------|-----------|------------|---------|---------|---------|---------------|
| Access by index | O(1) | O(n) | — | — | — | — |
| Search | O(n) | O(n) | O(1) avg | O(log n) | O(1) avg | O(n) |
| Insert (end) | O(1) amort | O(1) | O(1) avg | O(log n) | O(1) avg | O(log n) |
| Insert (mid) | O(n) | O(1) | — | — | — | — |
| Delete | O(n) | O(1) | O(1) avg | O(log n) | O(1) avg | O(log n) |

---

*Topics progress from JVM foundations → language features → concurrency → modern Java → design patterns. Studying in order ensures each concept has the necessary context from prior sections.*
