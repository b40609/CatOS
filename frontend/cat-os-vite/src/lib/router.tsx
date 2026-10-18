import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';

interface RouterContextType {
  path: string;
  navigate: (to: string) => void;
}

const RouterContext = createContext<RouterContextType>({
  path: '/',
  navigate: () => {},
});

function normalizeRoutePath(raw: string): string {
  if (!raw) return '/';
  // Strip query string and fragment hashes
  const clean = raw.split('?')[0].split('#')[0].trim();
  if (!clean || clean === '/') return '/';
  // Ensure starts with /
  const withLeading = clean.startsWith('/') ? clean : `/${clean}`;
  // Strip trailing slash except root
  return withLeading.length > 1 && withLeading.endsWith('/')
    ? withLeading.slice(0, -1)
    : withLeading;
}

export function RouterProvider({ children }: { children: ReactNode }) {
  const getInitialPath = () => {
    if (typeof window === 'undefined') return '/';
    const hash = window.location.hash.replace(/^#/, '');
    if (hash && hash !== '/') {
      return normalizeRoutePath(hash);
    }
    const pathname = window.location.pathname;
    if (pathname && pathname !== '/') {
      return normalizeRoutePath(pathname);
    }
    return '/';
  };

  const [path, setPath] = useState<string>(getInitialPath);

  useEffect(() => {
    const handleUrlChange = () => {
      const hash = window.location.hash.replace(/^#/, '');
      if (hash && hash !== '/') {
        setPath(normalizeRoutePath(hash));
        return;
      }
      const pathname = window.location.pathname;
      if (pathname && pathname !== '/') {
        setPath(normalizeRoutePath(pathname));
        return;
      }
      setPath('/');
    };

    window.addEventListener('hashchange', handleUrlChange);
    window.addEventListener('popstate', handleUrlChange);
    return () => {
      window.removeEventListener('hashchange', handleUrlChange);
      window.removeEventListener('popstate', handleUrlChange);
    };
  }, []);

  const navigate = (to: string) => {
    const norm = normalizeRoutePath(to);
    window.location.hash = norm;
    setPath(norm);
  };

  return (
    <RouterContext.Provider value={{ path, navigate }}>
      {children}
    </RouterContext.Provider>
  );
}

export function useRouter() {
  return useContext(RouterContext);
}

export function useRouterState<T>(options?: { select?: (state: { location: { pathname: string } }) => T }): T {
  const { path } = useContext(RouterContext);
  if (options?.select) {
    return options.select({ location: { pathname: path } });
  }
  return path as unknown as T;
}

export function Link({
  to,
  children,
  className,
  activeProps,
  inactiveProps,
  activeOptions,
  ...props
}: {
  to: string;
  children: ReactNode;
  className?: string;
  activeProps?: { className?: string };
  inactiveProps?: { className?: string };
  activeOptions?: { exact?: boolean };
  [key: string]: any;
}) {
  const { path, navigate } = useContext(RouterContext);
  const isExact = activeOptions?.exact ?? (to === '/');
  const isActive = isExact ? path === to : (path === to || (to !== '/' && path.startsWith(to)));

  const combinedClass = [
    className,
    isActive ? activeProps?.className : inactiveProps?.className,
  ].filter(Boolean).join(' ');

  return (
    <a
      href={`#${to}`}
      onClick={(e) => {
        e.preventDefault();
        navigate(to);
      }}
      className={combinedClass}
      {...props}
    >
      {children}
    </a>
  );
}

export function createFileRoute(_path: string) {
  return (config: { component?: any; [key: string]: any }) => config;
}
