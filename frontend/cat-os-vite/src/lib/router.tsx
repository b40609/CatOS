import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';

interface RouterContextType {
  path: string;
  navigate: (to: string) => void;
}

const RouterContext = createContext<RouterContextType>({
  path: '/',
  navigate: () => {},
});

export function RouterProvider({ children }: { children: ReactNode }) {
  const getInitialPath = () => {
    const hash = window.location.hash.replace(/^#/, '');
    return hash.startsWith('/') ? hash : '/';
  };

  const [path, setPath] = useState<string>(getInitialPath);

  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash.replace(/^#/, '');
      setPath(hash.startsWith('/') ? hash : '/');
    };
    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  const navigate = (to: string) => {
    window.location.hash = to;
    setPath(to);
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
