import { QueryClient } from "@tanstack/react-query";
import { createRouter } from "@tanstack/react-router";
import { routeTree } from "./routeTree.gen";

function getBasepath() {
  const raw = import.meta.env.VITE_BASE_PATH ?? "/";
  const normalized = raw.startsWith("/") ? raw : `/${raw}`;
  const withoutTrailingSlash = normalized.replace(/\/+$/, "");

  return withoutTrailingSlash || "/";
}

export const getRouter = () => {
  const queryClient = new QueryClient();

  const router = createRouter({
    routeTree,
    basepath: getBasepath(),
    context: { queryClient },
    scrollRestoration: true,
    defaultPreloadStaleTime: 0,
  });

  return router;
};
