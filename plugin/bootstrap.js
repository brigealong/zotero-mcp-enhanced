/**
 * Most of this code is from Zotero team's official Make It Red example[1]
 * or the Zotero 7 documentation[2].
 * [1] https://github.com/zotero/make-it-red
 * [2] https://www.zotero.org/support/dev/zotero_7_for_developers
 */

var chromeHandle;
var storedAttachmentPoCContext;

const markerDir = PathUtils.join(PathUtils.tempDir, "zotero-mcp-enhanced");
const bootstrapProbePath = `${markerDir}\\bootstrap-probe.json`;
const bootstrapStagePath = `${markerDir}\\bootstrap-stage.txt`;

async function writeBootstrapProbe(stage, details = {}) {
  try {
    await IOUtils.makeDirectory(markerDir, { createAncestors: true });
    await IOUtils.writeUTF8(bootstrapStagePath, stage);
    await IOUtils.writeUTF8(
      bootstrapProbePath,
      JSON.stringify(
        {
          stage,
          occurredAt: new Date().toISOString(),
          ...details,
        },
        null,
        2,
      ),
    );
  }
  catch (err) {
    try {
      Zotero.logError(err);
    }
    catch (_probeErr) {}
  }
}

function install(data, reason) {}

async function startup({ id, version, resourceURI, rootURI }, reason) {
  await writeBootstrapProbe("startup-entered", { id, version, reason, rootURI });

  try {
    var aomStartup = Components.classes[
      "@mozilla.org/addons/addon-manager-startup;1"
    ].getService(Components.interfaces.amIAddonManagerStartup);
    var manifestURI = Services.io.newURI(rootURI + "manifest.json");
    chromeHandle = aomStartup.registerChrome(manifestURI, [
      ["content", "storedattachmentpoc", rootURI + "content/"],
    ]);
    await writeBootstrapProbe("after-register-chrome");

    /**
     * Global variables for plugin code.
     * The `_globalThis` is the global root variable of the plugin sandbox environment
     * and all child variables assigned to it is globally accessible.
     * See `src/index.ts` for details.
     */
    const ctx = { rootURI };
    ctx._globalThis = ctx;
    storedAttachmentPoCContext = ctx;

    await writeBootstrapProbe("before-load-subscript");
    Services.scriptloader.loadSubScript(
      `${rootURI}/content/scripts/storedattachmentpoc.js`,
      ctx,
    );
    await writeBootstrapProbe("after-load-subscript", {
      contextKeys: Object.keys(ctx).sort(),
      hasStoredAttachmentPoC: !!ctx.StoredAttachmentPoC,
    });

    if (!ctx.StoredAttachmentPoC?.hooks?.onStartup) {
      throw new Error("StoredAttachmentPoC.hooks.onStartup is not available after loadSubScript()");
    }

    await writeBootstrapProbe("before-onStartup-hook");
    await ctx.StoredAttachmentPoC.hooks.onStartup();
    await writeBootstrapProbe("after-onStartup-hook");
  }
  catch (err) {
    await writeBootstrapProbe("startup-error", {
      error: String(err),
      stack: err?.stack || null,
    });
    throw err;
  }
}

async function onMainWindowLoad({ window }, reason) {
  await storedAttachmentPoCContext?.StoredAttachmentPoC?.hooks?.onMainWindowLoad(window);
}

async function onMainWindowUnload({ window }, reason) {
  await storedAttachmentPoCContext?.StoredAttachmentPoC?.hooks?.onMainWindowUnload(window);
}

async function shutdown({ id, version, resourceURI, rootURI }, reason) {
  if (reason === APP_SHUTDOWN) {
    return;
  }

  await storedAttachmentPoCContext?.StoredAttachmentPoC?.hooks?.onShutdown();

  if (chromeHandle) {
    chromeHandle.destruct();
    chromeHandle = null;
  }
}

async function uninstall(data, reason) {}
