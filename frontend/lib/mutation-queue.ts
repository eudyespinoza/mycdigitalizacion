export function createSerializedQueue() {
  let tail: Promise<unknown> = Promise.resolve();
  return {
    enqueue<T>(operation: () => Promise<T>) {
      const run = tail.catch(() => undefined).then(operation);
      tail = run.catch(() => undefined);
      return run;
    },
  };
}
