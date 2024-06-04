import * as npmPlugin from "./plugins/npm/ui";
import * as pythonPlugin from "./plugins/python/ui";
export function InitPlugins() {
  // Load all plugins
  npmPlugin.init();
  pythonPlugin.init();
}
