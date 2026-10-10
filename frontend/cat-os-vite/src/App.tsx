import React, { useEffect } from 'react';
import { RouterProvider, useRouter } from '@/lib/router';
import { AuthProvider } from '@/lib/auth';
import { stateAdapter } from '@/state/stateAdapter';

// Import Page Routes
import { Route as DashboardRoute } from '@/pages/index';
import { Route as BotsRoute } from '@/pages/bots';
import { Route as RiskRoute } from '@/pages/risk';
import { Route as StrategiesRoute } from '@/pages/strategies';
import { Route as LogsRoute } from '@/pages/logs';
import { Route as SettingsRoute } from '@/pages/settings';
import { Route as BacktestRoute } from '@/pages/backtest';
import { Route as OptimizationRoute } from '@/pages/optimization';
import { Route as ProfileRoute } from '@/pages/profile';
import { Route as ReviewRoute } from '@/pages/review';
import { Route as MarketIntelRoute } from '@/pages/market-intel';

const routeMap: Record<string, React.ComponentType> = {
  '/': DashboardRoute.component,
  '/bots': BotsRoute.component,
  '/risk': RiskRoute.component,
  '/strategies': StrategiesRoute.component,
  '/logs': LogsRoute.component,
  '/settings': SettingsRoute.component,
  '/backtest': BacktestRoute.component,
  '/optimization': OptimizationRoute.component,
  '/profile': ProfileRoute.component,
  '/review': ReviewRoute.component,
  '/market-intel': MarketIntelRoute.component,
};

function RouterView() {
  const { path } = useRouter();
  const Component = routeMap[path] || DashboardRoute.component;

  // Initialize CatOS authoritative state once
  useEffect(() => {
    stateAdapter.init('normal').catch(console.error);
  }, []);

  return <Component />;
}

export function App() {
  return (
    <AuthProvider>
      <RouterProvider>
        <RouterView />
      </RouterProvider>
    </AuthProvider>
  );
}

export default App;
