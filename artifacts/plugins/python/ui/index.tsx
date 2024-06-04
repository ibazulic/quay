import React, { useEffect } from "react";
import { PluginSidebarNavItems } from "src/atoms/SidebarState";
import { useRecoilState } from "recoil";
import { SideNavProps } from "src/components/sidebar/QuaySidebar";
import { PluginNavigationRoutes } from "src/atoms/Routes";
import { NavigationRoute } from "src/routes/NavigationPath";
import { PythonPackagesList } from "./PythonPackagesList";
import RepositoryDetails from "src/routes/RepositoryDetails/RepositoryDetails";

export function init() {
  const [pluginSidebarNavItems, setPluginSidebarNavItems] = useRecoilState<
    SideNavProps[]
  >(PluginSidebarNavItems);
  const [pluginRoutes, setPluginRoutes] = useRecoilState<NavigationRoute[]>(
    PluginNavigationRoutes,
  );
  useEffect(() => {
    // TODO: check if plugin is enabled
    setPluginSidebarNavItems((prevItems) => {
      return [
        ...prevItems,
        {
          isSideNav: true,
          navPath: "python",
          title: "Python Packages",
          component: <PythonPackagesList />,
        },
      ] as SideNavProps[];
    });

    setPluginRoutes((prevRoutes) => {
      return [
        ...prevRoutes,
        {
          path: "/python",
          Component: <PythonPackagesList />,
        },
        {
          path: "/python/repository",
          Component: <PythonPackagesList />,
        },
        {
          path: "/python/repository/:organizationName/*",
          Component: <RepositoryDetails />,
        },
      ] as NavigationRoute[];
    });
  }, []);
}
