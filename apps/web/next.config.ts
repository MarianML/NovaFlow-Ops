import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  turbopack: {
    // Fuerza a Next/Turbopack a tratar apps/web como root,
    // y no C:\Users\MarianDark por culpa de lockfiles.
    root: path.join(__dirname),
  },
};

export default nextConfig;
