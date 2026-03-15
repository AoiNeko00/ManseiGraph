declare module 'd3-force-3d' {
  export function forceCollide(radius?: number | ((node: any) => number)): {
    radius(r: number | ((node: any) => number)): ReturnType<typeof forceCollide>;
    strength(s: number): ReturnType<typeof forceCollide>;
    iterations(i: number): ReturnType<typeof forceCollide>;
  };
}
