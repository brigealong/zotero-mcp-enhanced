const markerDir = PathUtils.join(PathUtils.tempDir, "zotero-mcp-enhanced");
const markerJson = `${markerDir}\\startup-entered.json`;
const markerTxt = `${markerDir}\\startup-stage.txt`;
const legacyConfigPath = `${markerDir}\\run.json`;
const legacyDefaultResultPath = `${markerDir}\\result.json`;
const commandsDir = `${markerDir}\\commands`;
const resultsDir = `${markerDir}\\results`;
const pollIntervalMs = 2000;

const ACTION_IMPORT = "import";
const ACTION_IMPORT_STORED_ATTACHMENT = "importStoredAttachment";
const ACTION_CREATE_ITEM = "createItem";
const ACTION_UPDATE_ITEM_FIELDS = "updateItemFields";
const ACTION_ADD_ITEM_TO_COLLECTIONS = "addItemToCollections";
const ACTION_CREATE_NOTE = "createNote";
const ACTION_UPDATE_NOTE = "updateNote";
const ACTION_CREATE_COLLECTION = "createCollection";
const ACTION_MOVE_COLLECTION = "moveCollection";
const ACTION_REMOVE_ITEM_FROM_COLLECTIONS = "removeItemFromCollections";
const ACTION_TRASH_ATTACHMENT = "trashAttachment";
const ACTION_TRASH_NOTE = "trashNote";
const ACTION_TRASH_REGULAR_ITEM = "trashRegularItem";
const ACTION_CREATE_ANNOTATION = "createAnnotation";
const ACTION_RUN_TRANSACTION = "runTransaction";

const SUPPORTED_ITEM_TYPES = [
  "book",
  "journalArticle",
  "bookSection",
  "webpage",
  "document",
];

const SUPPORTED_CREATOR_TYPES = [
  "author",
  "editor",
  "translator",
  "bookAuthor",
];

const SUPPORTED_NOTE_UPDATE_MODES = [
  "replace",
  "append",
  "prepend",
];

const SUPPORTED_ANNOTATION_TYPES = [
  "note",
  "highlight",
  "underline",
];

function getParentDir(path) {
  return path.replace(/[\\/][^\\/]+$/, "");
}

async function ensureParentDir(path) {
  const parentDir = getParentDir(path);
  if (!parentDir || parentDir === path) {
    return;
  }
  await IOUtils.makeDirectory(parentDir, { createAncestors: true });
}

async function ensureQueueDirs() {
  await IOUtils.makeDirectory(commandsDir, { createAncestors: true });
  await IOUtils.makeDirectory(resultsDir, { createAncestors: true });
}

function pathExists(path) {
  try {
    return Zotero.File.pathToFile(path).exists();
  }
  catch (err) {
    Zotero.logError(err);
    return false;
  }
}

async function writeText(path, value) {
  await ensureParentDir(path);
  return IOUtils.writeUTF8(path, value);
}

async function writeJson(path, value) {
  return writeText(path, JSON.stringify(value, null, 2));
}

async function readText(path) {
  return IOUtils.readUTF8(path);
}

async function tryReadJson(path) {
  if (!path || !pathExists(path)) {
    return null;
  }
  return JSON.parse(await readText(path));
}

async function removePath(path) {
  if (!path || !pathExists(path)) {
    return;
  }
  try {
    await IOUtils.remove(path);
  }
  catch (err) {
    Zotero.logError(err);
  }
}

async function writeStage(stage) {
  try {
    await writeText(markerTxt, stage);
  }
  catch (err) {
    Zotero.logError(err);
  }
}

async function writeResult(path, payload) {
  try {
    await writeJson(path || legacyDefaultResultPath, payload);
  }
  catch (err) {
    Zotero.logError(err);
  }
}

function normalizeAction(action) {
  switch (action) {
    case ACTION_IMPORT:
    case ACTION_IMPORT_STORED_ATTACHMENT:
      return ACTION_IMPORT_STORED_ATTACHMENT;
    case ACTION_CREATE_ITEM:
    case ACTION_UPDATE_ITEM_FIELDS:
    case ACTION_ADD_ITEM_TO_COLLECTIONS:
    case ACTION_CREATE_NOTE:
    case ACTION_UPDATE_NOTE:
    case ACTION_CREATE_COLLECTION:
    case ACTION_MOVE_COLLECTION:
    case ACTION_REMOVE_ITEM_FROM_COLLECTIONS:
    case ACTION_TRASH_ATTACHMENT:
    case ACTION_TRASH_NOTE:
    case ACTION_TRASH_REGULAR_ITEM:
    case ACTION_CREATE_ANNOTATION:
    case ACTION_RUN_TRANSACTION:
      return action;
    default:
      return ACTION_IMPORT_STORED_ATTACHMENT;
  }
}

function normalizeRequestSignature(config) {
  const action = normalizeAction(config.action);
  if (config.requestID) {
    return `request:${action}:${config.requestID}`;
  }

  const libraryID = config.libraryID ?? Zotero.Libraries.userLibraryID;
  return [
    "legacy",
    action,
    libraryID,
    config.parentKey || "",
    config.itemKey || "",
    config.filePath || "",
    config.fileBaseName || "",
  ].join("|");
}

function buildResultPayload(base, extra = {}) {
  return {
    requestID: base.requestID ?? null,
    requestSignature: base.requestSignature,
    status: base.status,
    occurredAt: new Date().toISOString(),
    ...extra,
  };
}

function getResultPathForConfig(config) {
  if (config.resultPath) {
    return config.resultPath;
  }
  if (config.requestID) {
    return `${resultsDir}\\result-${config.requestID}.json`;
  }
  return legacyDefaultResultPath;
}

async function getNextPendingCommandPath() {
  await ensureQueueDirs();
  const children = await IOUtils.getChildren(commandsDir);
  return children
    .filter((path) => path.endsWith(".json"))
    .sort((a, b) => a.localeCompare(b))[0] || null;
}

function ensurePlainObject(value, label) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`${label} must be an object`);
  }
}

function ensureArray(value, label) {
  if (!Array.isArray(value)) {
    throw new Error(`${label} must be an array`);
  }
}

function asArray(value) {
  if (value === null || value === undefined) {
    return [];
  }
  return Array.isArray(value) ? value : [value];
}

function normalizeFieldValue(value) {
  if (value === null || value === undefined) {
    return "";
  }
  return String(value);
}

function setItemFields(item, fields) {
  ensurePlainObject(fields, "fields");
  for (const [field, value] of Object.entries(fields)) {
    item.setField(field, normalizeFieldValue(value));
  }
}

function normalizeCreators(creators) {
  if (!creators) {
    return [];
  }
  return asArray(creators).map((creator, index) => {
    ensurePlainObject(creator, `creators[${index}]`);
    const creatorType = creator.creatorType || "author";
    if (!SUPPORTED_CREATOR_TYPES.includes(creatorType)) {
      throw new Error(`Unsupported creatorType: ${creatorType}`);
    }
    return {
      firstName: normalizeFieldValue(creator.firstName || ""),
      lastName: normalizeFieldValue(creator.lastName || ""),
      creatorType,
      fieldMode: creator.fieldMode ? Number(creator.fieldMode) : 0,
    };
  });
}

function normalizeTags(tags) {
  if (!tags) {
    return [];
  }
  return asArray(tags).map((tag) => ({
    tag: normalizeFieldValue(tag),
  }));
}

function getItemByLibraryAndKeyOrThrow(libraryID, itemKey, label = "Item") {
  const item = Zotero.Items.getByLibraryAndKey(libraryID, itemKey);
  if (!item) {
    throw new Error(`${label} not found: libraryID=${libraryID}, key=${itemKey}`);
  }
  return item;
}

function getCollectionByLibraryAndKeyOrThrow(libraryID, collectionKey) {
  const collection = Zotero.Collections.getByLibraryAndKey(libraryID, collectionKey);
  if (!collection) {
    throw new Error(`Collection not found: libraryID=${libraryID}, key=${collectionKey}`);
  }
  return collection;
}

function resolveCollectionIDs(libraryID, collectionKeys = []) {
  if (!collectionKeys || collectionKeys.length === 0) {
    return [];
  }
  return asArray(collectionKeys).map((collectionKey) =>
    getCollectionByLibraryAndKeyOrThrow(libraryID, collectionKey).id
  );
}

function isNoteItem(item) {
  return typeof item.isNote === "function" ? item.isNote() : false;
}

function isAttachmentItem(item) {
  return typeof item.isAttachment === "function" ? item.isAttachment() : false;
}

function isRegularItem(item) {
  if (typeof item.isRegularItem === "function") {
    return item.isRegularItem();
  }
  return !isNoteItem(item) && !isAttachmentItem(item);
}

function buildItemSnapshot(item, fields = []) {
  const snapshot = {};
  for (const field of fields) {
    snapshot[field] = item.getField(field);
  }
  return snapshot;
}

function buildCollectionSnapshots(libraryID, collectionKeys = []) {
  return asArray(collectionKeys).map((collectionKey) => {
    const collection = getCollectionByLibraryAndKeyOrThrow(libraryID, collectionKey);
    const parentCollectionID = collection.parentID || null;
    return {
      collectionID: collection.id,
      collectionKey: collection.key,
      collectionName: collection.name,
      parentCollectionID,
    };
  });
}

function buildCollectionSnapshot(collection) {
  if (!collection) {
    return null;
  }
  const parentCollectionID = collection.parentID || null;
  return {
    collectionID: collection.id,
    collectionKey: collection.key,
    collectionName: collection.name,
    parentCollectionID,
    parentCollectionKey: parentCollectionID ? Zotero.Collections.get(parentCollectionID)?.key || null : null,
  };
}

function normalizeAnnotationPosition(position, fallbackPageIndex = null) {
  ensurePlainObject(position, "position");
  const normalized = { ...position };

  if (normalized.pageIndex === undefined || normalized.pageIndex === null || normalized.pageIndex === "") {
    if (fallbackPageIndex === null || fallbackPageIndex === undefined) {
      throw new Error("position.pageIndex is required");
    }
    normalized.pageIndex = Number(fallbackPageIndex);
  }
  else {
    normalized.pageIndex = Number(normalized.pageIndex);
  }

  if (!Number.isInteger(normalized.pageIndex) || normalized.pageIndex < 0) {
    throw new Error(`Invalid position.pageIndex: ${normalized.pageIndex}`);
  }

  ensureArray(normalized.rects, "position.rects");
  normalized.rects = normalized.rects.map((rect, index) => {
    if (!Array.isArray(rect) || rect.length !== 4) {
      throw new Error(`position.rects[${index}] must be an array of four numbers`);
    }
    return rect.map((value, rectIndex) => {
      const numeric = Number(value);
      if (!Number.isFinite(numeric)) {
        throw new Error(`position.rects[${index}][${rectIndex}] must be numeric`);
      }
      return numeric;
    });
  });

  return normalized;
}

function buildSyntheticAnnotationSortIndex(position) {
  const rect = position.rects[0] || [0, 0, 0, 0];
  const syntheticOffset = 0;
  const syntheticTop = Math.max(0, Math.min(99999, Math.floor(100000 - (rect[3] || 0))));
  return [
    position.pageIndex.toString().slice(0, 5).padStart(5, "0"),
    syntheticOffset.toString().slice(0, 6).padStart(6, "0"),
    syntheticTop.toString().slice(0, 5).padStart(5, "0"),
  ].join("|");
}

function parseStepReference(value) {
  if (typeof value !== "string") {
    return null;
  }
  const match = value.match(/^step:(\d+):([A-Za-z0-9_.-]+)$/);
  if (!match) {
    return null;
  }
  return {
    stepIndex: Number(match[1]),
    field: match[2],
  };
}

function resolveFieldPath(source, path) {
  return path.split(".").reduce((current, segment) => {
    if (current === null || current === undefined) {
      return undefined;
    }
    return current[segment];
  }, source);
}

function resolveStepReferences(value, stepResults) {
  const ref = parseStepReference(value);
  if (ref) {
    const stepResult = stepResults[ref.stepIndex];
    if (!stepResult) {
      throw new Error(`Step reference not found: ${value}`);
    }
    const resolved = resolveFieldPath(stepResult, ref.field);
    if (resolved === undefined) {
      throw new Error(`Step reference field not found: ${value}`);
    }
    return resolved;
  }

  if (Array.isArray(value)) {
    return value.map((entry) => resolveStepReferences(entry, stepResults));
  }

  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, entry]) => [
        key,
        resolveStepReferences(entry, stepResults),
      ])
    );
  }

  return value;
}

class TransactionStepError extends Error {
  constructor(message, failedStepIndex, stepResults) {
    super(message);
    this.name = "TransactionStepError";
    this.failedStepIndex = failedStepIndex;
    this.stepResults = stepResults;
  }
}

var StoredAttachmentPoC = {
  pollTimer: null,
  isProcessing: false,
  lastCompletedRequestID: null,
  currentRequestID: null,

  hooks: {
    async onStartup() {
      await Zotero.initializationPromise;
      await ensureQueueDirs();
      await writeStage("watcher-ready");

      await StoredAttachmentPoC.maybeProcessPendingJob("startup");
      StoredAttachmentPoC.startPolling();
    },

    async onMainWindowLoad() {},

    async onMainWindowUnload() {},

    async onShutdown() {
      if (StoredAttachmentPoC.pollTimer) {
        clearInterval(StoredAttachmentPoC.pollTimer);
        StoredAttachmentPoC.pollTimer = null;
      }
    },
  },

  startPolling() {
    if (this.pollTimer) {
      return;
    }

    this.pollTimer = setInterval(() => {
      void this.maybeProcessPendingJob("poll");
    }, pollIntervalMs);
  },

  async maybeProcessPendingJob(trigger) {
    if (this.isProcessing) {
      return;
    }

    const commandPath = await getNextPendingCommandPath();
    if (!commandPath && !pathExists(legacyConfigPath)) {
      return;
    }

    let config;
    try {
      if (commandPath) {
        config = JSON.parse(await readText(commandPath));
      }
      else {
        config = JSON.parse(await readText(legacyConfigPath));
      }
    }
    catch (err) {
      await writeStage("config-read-failed");
      Zotero.logError(err);
      if (commandPath) {
        await removePath(commandPath);
      }
      return;
    }

    config = {
      ...config,
      action: normalizeAction(config.action),
      resultPath: getResultPathForConfig(config),
      __commandPath: commandPath || null,
    };

    const requestSignature = normalizeRequestSignature(config);
    if (requestSignature === this.currentRequestID || requestSignature === this.lastCompletedRequestID) {
      if (config.__commandPath) {
        await removePath(config.__commandPath);
      }
      return;
    }

    this.isProcessing = true;
    this.currentRequestID = requestSignature;

    try {
      await this.processJob({
        ...config,
        requestSignature,
      }, trigger);
      this.lastCompletedRequestID = requestSignature;
    }
    finally {
      this.currentRequestID = null;
      this.isProcessing = false;
    }
  },

  async processJob(config, trigger) {
    const resultPath = config.resultPath || legacyDefaultResultPath;

    try {
      await writeJson(markerJson, buildResultPayload({
        requestID: config.requestID,
        requestSignature: config.requestSignature,
        status: "entered",
      }, {
        action: config.action,
        trigger,
      }));
      await writeStage("entered");

      const existing = await tryReadJson(resultPath);
      if (existing?.status === "success") {
        const matchedByRequestID = config.requestID && existing.requestID === config.requestID;
        const matchedBySignature = existing.requestSignature === config.requestSignature;
        const matchedLegacyPair = !config.requestID
          && existing.parentKey === config.parentKey
          && existing.sourcePath === config.filePath;

        if (matchedByRequestID || matchedBySignature || matchedLegacyPair) {
          await writeStage("existing-success-result");
          return;
        }
      }

      await writeStage(`before-${config.action}`);
      const actionResult = await this.dispatchAction(config);
      const result = buildResultPayload({
        requestID: config.requestID,
        requestSignature: config.requestSignature,
        status: "success",
      }, {
        action: config.action,
        trigger,
        ...actionResult,
      });

      await writeResult(resultPath, result);
      await writeStage(`after-${config.action}-success-write`);

      if (config.alertOnSuccess) {
        Services.prompt.alert(
          null,
          "Stored Attachment PoC",
          `${config.action} succeeded\nrequestID: ${result.requestID}`,
        );
      }
    }
    catch (err) {
      await writeStage("in-catch");
      const failure = buildResultPayload({
        requestID: config.requestID,
        requestSignature: config.requestSignature,
        status: "error",
      }, {
        action: config.action,
        trigger,
        error: String(err),
        stack: err?.stack || null,
        failedStepIndex: err?.failedStepIndex ?? null,
        stepResults: err?.stepResults || null,
        configPath: config.__commandPath || legacyConfigPath,
        resultPath,
      });
      await writeResult(resultPath, failure);
      Zotero.logError(err);

      if (config.alertOnError) {
        Services.prompt.alert(
          null,
          "Stored Attachment PoC",
          `${config.action} failed\n${failure.error}`,
        );
      }
    }
    finally {
      if (config.__commandPath) {
        await removePath(config.__commandPath);
      }
    }
  },

  async dispatchAction(config) {
    switch (config.action) {
      case ACTION_IMPORT_STORED_ATTACHMENT:
        return this.processImportStoredAttachmentJob(config);
      case ACTION_CREATE_ITEM:
        return this.processCreateItemJob(config);
      case ACTION_UPDATE_ITEM_FIELDS:
        return this.processUpdateItemFieldsJob(config);
      case ACTION_ADD_ITEM_TO_COLLECTIONS:
        return this.processAddItemToCollectionsJob(config);
      case ACTION_CREATE_NOTE:
        return this.processCreateNoteJob(config);
      case ACTION_UPDATE_NOTE:
        return this.processUpdateNoteJob(config);
      case ACTION_CREATE_COLLECTION:
        return this.processCreateCollectionJob(config);
      case ACTION_MOVE_COLLECTION:
        return this.processMoveCollectionJob(config);
      case ACTION_REMOVE_ITEM_FROM_COLLECTIONS:
        return this.processRemoveItemFromCollectionsJob(config);
      case ACTION_TRASH_ATTACHMENT:
        return this.processTrashAttachmentJob(config);
      case ACTION_TRASH_NOTE:
        return this.processTrashNoteJob(config);
      case ACTION_TRASH_REGULAR_ITEM:
        return this.processTrashRegularItemJob(config);
      case ACTION_CREATE_ANNOTATION:
        return this.processCreateAnnotationJob(config);
      case ACTION_RUN_TRANSACTION:
        return this.processRunTransactionJob(config);
      default:
        throw new Error(`Unsupported action: ${config.action}`);
    }
  },

  async processImportStoredAttachmentJob(config) {
    const libraryID = config.libraryID ?? Zotero.Libraries.userLibraryID;
    const parentItem = getItemByLibraryAndKeyOrThrow(libraryID, config.parentKey, "Parent item");

    if (!config.filePath || !pathExists(config.filePath)) {
      throw new Error(`Source file not found: ${config.filePath}`);
    }

    const imported = await Zotero.Attachments.importFromFile({
      file: config.filePath,
      fileBaseName: config.fileBaseName,
      libraryID,
      parentItemID: parentItem.id,
    });

    const attachmentItem = typeof imported === "number" ? Zotero.Items.get(imported) : imported;
    if (!attachmentItem) {
      throw new Error("Import returned no attachment item");
    }

    const importedPath = attachmentItem.getFilePath();
    return {
      libraryID,
      parentItemID: parentItem.id,
      parentKey: parentItem.key,
      sourcePath: config.filePath,
      attachmentID: attachmentItem.id,
      attachmentKey: attachmentItem.key,
      attachmentTitle: attachmentItem.getField("title"),
      attachmentLinkMode: attachmentItem.attachmentLinkMode,
      isStored: typeof attachmentItem.isStoredFileAttachment === "function"
        ? attachmentItem.isStoredFileAttachment()
        : attachmentItem.attachmentLinkMode === Zotero.Attachments.LINK_MODE_IMPORTED_FILE,
      importedPath,
      importedExists: importedPath ? pathExists(importedPath) : false,
      childCountAfterImport: parentItem.getAttachments().length,
    };
  },

  async processCreateItemJob(config) {
    const libraryID = config.libraryID ?? Zotero.Libraries.userLibraryID;
    const itemType = config.itemType;
    if (!SUPPORTED_ITEM_TYPES.includes(itemType)) {
      throw new Error(`Unsupported itemType: ${itemType}`);
    }

    ensurePlainObject(config.fields, "fields");
    if (!config.fields.title) {
      throw new Error("fields.title is required");
    }

    const item = new Zotero.Item(itemType);
    item.libraryID = libraryID;
    setItemFields(item, config.fields);

    const creators = normalizeCreators(config.creators);
    if (creators.length > 0) {
      item.setCreators(creators);
    }

    const collectionIDs = resolveCollectionIDs(libraryID, config.collectionKeys || []);
    if (collectionIDs.length > 0) {
      item.setCollections(collectionIDs);
    }

    const tags = normalizeTags(config.tags);
    if (tags.length > 0 && typeof item.setTags === "function") {
      item.setTags(tags);
    }

    const itemID = await item.saveTx();
    const savedItem = Zotero.Items.get(itemID);
    return {
      libraryID,
      itemID: savedItem.id,
      itemKey: savedItem.key,
      itemType,
      fields: buildItemSnapshot(savedItem, Object.keys(config.fields)),
      creators,
      collections: buildCollectionSnapshots(libraryID, config.collectionKeys || []),
    };
  },

  async processUpdateItemFieldsJob(config) {
    const libraryID = config.libraryID ?? Zotero.Libraries.userLibraryID;
    const item = getItemByLibraryAndKeyOrThrow(libraryID, config.itemKey);
    ensurePlainObject(config.fields, "fields");
    setItemFields(item, config.fields);
    await item.saveTx();

    return {
      libraryID,
      itemID: item.id,
      itemKey: item.key,
      updatedFields: buildItemSnapshot(item, Object.keys(config.fields)),
    };
  },

  async processAddItemToCollectionsJob(config) {
    const libraryID = config.libraryID ?? Zotero.Libraries.userLibraryID;
    const item = getItemByLibraryAndKeyOrThrow(libraryID, config.itemKey);
    const collectionIDs = resolveCollectionIDs(libraryID, config.collectionKeys || []);
    for (const collectionID of collectionIDs) {
      item.addToCollection(collectionID);
    }
    await item.saveTx();

    return {
      libraryID,
      itemID: item.id,
      itemKey: item.key,
      collections: buildCollectionSnapshots(libraryID, config.collectionKeys || []),
      collectionCountAfterUpdate: item.getCollections().length,
    };
  },

  async processCreateNoteJob(config) {
    const libraryID = config.libraryID ?? Zotero.Libraries.userLibraryID;
    if (!config.content) {
      throw new Error("content is required");
    }

    const note = new Zotero.Item("note");
    note.libraryID = libraryID;
    note.setNote(String(config.content));

    if (config.parentKey) {
      const parentItem = getItemByLibraryAndKeyOrThrow(libraryID, config.parentKey, "Parent item");
      note.parentID = parentItem.id;
    }

    const collectionIDs = resolveCollectionIDs(libraryID, config.collectionKeys || []);
    if (collectionIDs.length > 0) {
      note.setCollections(collectionIDs);
    }

    const itemID = await note.saveTx();
    const savedNote = Zotero.Items.get(itemID);
    return {
      libraryID,
      itemID: savedNote.id,
      itemKey: savedNote.key,
      parentItemID: savedNote.parentID || null,
      parentKey: savedNote.parentID ? Zotero.Items.get(savedNote.parentID).key : null,
      noteLength: savedNote.getNote().length,
      collections: buildCollectionSnapshots(libraryID, config.collectionKeys || []),
    };
  },

  async processUpdateNoteJob(config) {
    const libraryID = config.libraryID ?? Zotero.Libraries.userLibraryID;
    const note = getItemByLibraryAndKeyOrThrow(libraryID, config.itemKey, "Note item");
    if (!isNoteItem(note)) {
      throw new Error(`Item is not a note: libraryID=${libraryID}, key=${config.itemKey}`);
    }

    const mode = config.mode || "replace";
    if (!SUPPORTED_NOTE_UPDATE_MODES.includes(mode)) {
      throw new Error(`Unsupported updateNote mode: ${mode}`);
    }

    const currentNote = note.getNote() || "";
    const incoming = String(config.content || "");
    let nextNote = incoming;
    if (mode === "append") {
      nextNote = currentNote + incoming;
    }
    else if (mode === "prepend") {
      nextNote = incoming + currentNote;
    }

    note.setNote(nextNote);
    await note.saveTx();

    return {
      libraryID,
      itemID: note.id,
      itemKey: note.key,
      mode,
      noteLength: note.getNote().length,
    };
  },

  async processCreateCollectionJob(config) {
    const libraryID = config.libraryID ?? Zotero.Libraries.userLibraryID;
    const name = normalizeFieldValue(config.name);
    if (!name) {
      throw new Error("name is required");
    }

    const parentCollection = config.parentCollectionKey
      ? getCollectionByLibraryAndKeyOrThrow(libraryID, config.parentCollectionKey)
      : null;

    const collection = new Zotero.Collection;
    collection.libraryID = libraryID;
    collection.name = name;
    if (parentCollection) {
      collection.parentID = parentCollection.id;
    }

    const collectionID = await collection.saveTx();
    const savedCollection = Zotero.Collections.get(collectionID);
    const parentCollectionID = savedCollection.parentID || null;
    return {
      libraryID,
      collectionID: savedCollection.id,
      collectionKey: savedCollection.key,
      collectionName: savedCollection.name,
      parentCollectionID,
      parentCollectionKey: parentCollectionID ? Zotero.Collections.get(parentCollectionID)?.key || null : null,
    };
  },

  async processMoveCollectionJob(config) {
    const libraryID = config.libraryID ?? Zotero.Libraries.userLibraryID;
    const collection = getCollectionByLibraryAndKeyOrThrow(libraryID, config.collectionKey);
    const targetParent = config.parentCollectionKey
      ? getCollectionByLibraryAndKeyOrThrow(libraryID, config.parentCollectionKey)
      : null;

    if (targetParent && targetParent.id === collection.id) {
      throw new Error("A collection cannot be moved under itself");
    }

    const oldParent = collection.parentID ? Zotero.Collections.get(collection.parentID) : null;
    collection.parentID = targetParent ? targetParent.id : false;
    await collection.saveTx();
    const parentCollectionID = collection.parentID || null;

    return {
      libraryID,
      collectionID: collection.id,
      collectionKey: collection.key,
      collectionName: collection.name,
      previousParentCollection: buildCollectionSnapshot(oldParent),
      parentCollectionID,
      parentCollectionKey: parentCollectionID ? Zotero.Collections.get(parentCollectionID)?.key || null : null,
    };
  },

  async processRemoveItemFromCollectionsJob(config) {
    const libraryID = config.libraryID ?? Zotero.Libraries.userLibraryID;
    const item = getItemByLibraryAndKeyOrThrow(libraryID, config.itemKey);
    const collectionKeys = asArray(config.collectionKeys || []);
    const removedCollections = buildCollectionSnapshots(libraryID, collectionKeys);
    const collectionIDs = resolveCollectionIDs(libraryID, collectionKeys);
    for (const collectionID of collectionIDs) {
      item.removeFromCollection(collectionID);
    }
    await item.saveTx();

    return {
      libraryID,
      itemID: item.id,
      itemKey: item.key,
      removedCollections,
      collectionCountAfterUpdate: item.getCollections().length,
      collectionsAfterUpdate: item.getCollections().map((collectionID) => {
        const collection = Zotero.Collections.get(collectionID);
        return buildCollectionSnapshot(collection);
      }).filter(Boolean),
    };
  },

  async processTrashAttachmentJob(config) {
    const libraryID = config.libraryID ?? Zotero.Libraries.userLibraryID;
    const attachmentItem = getItemByLibraryAndKeyOrThrow(libraryID, config.itemKey, "Attachment item");
    if (!isAttachmentItem(attachmentItem)) {
      throw new Error(`Item is not an attachment: libraryID=${libraryID}, key=${config.itemKey}`);
    }

    const parentItem = attachmentItem.parentItemID ? Zotero.Items.get(attachmentItem.parentItemID) : null;
    const childCountBeforeTrash = parentItem ? parentItem.getAttachments().length : null;

    await Zotero.Items.trashTx([attachmentItem.id]);

    const trashedItem = Zotero.Items.get(attachmentItem.id);
    const childCountAfterTrash = parentItem ? parentItem.getAttachments().length : null;

    return {
      libraryID,
      itemID: attachmentItem.id,
      itemKey: attachmentItem.key,
      itemTitle: attachmentItem.getField("title"),
      parentItemID: parentItem ? parentItem.id : null,
      parentKey: parentItem ? parentItem.key : null,
      childCountBeforeTrash,
      childCountAfterTrash,
      trashed: !!(trashedItem && trashedItem.deleted),
    };
  },

  async processTrashNoteJob(config) {
    const libraryID = config.libraryID ?? Zotero.Libraries.userLibraryID;
    const note = getItemByLibraryAndKeyOrThrow(libraryID, config.itemKey, "Note item");
    if (!isNoteItem(note)) {
      throw new Error(`Item is not a note: libraryID=${libraryID}, key=${config.itemKey}`);
    }

    const parentItem = note.parentID ? Zotero.Items.get(note.parentID) : null;
    const notesBeforeTrash = parentItem ? parentItem.getNotes().length : null;
    await Zotero.Items.trashTx([note.id]);
    const trashedItem = Zotero.Items.get(note.id);

    return {
      libraryID,
      itemID: note.id,
      itemKey: note.key,
      parentItemID: parentItem ? parentItem.id : null,
      parentKey: parentItem ? parentItem.key : null,
      notesBeforeTrash,
      notesAfterTrash: parentItem ? parentItem.getNotes().length : null,
      trashed: !!(trashedItem && trashedItem.deleted),
    };
  },

  async processTrashRegularItemJob(config) {
    const libraryID = config.libraryID ?? Zotero.Libraries.userLibraryID;
    const item = getItemByLibraryAndKeyOrThrow(libraryID, config.itemKey, "Regular item");
    if (!isRegularItem(item)) {
      throw new Error(`Item is not a regular item: libraryID=${libraryID}, key=${config.itemKey}`);
    }

    const collectionCountBeforeTrash = item.getCollections().length;
    await Zotero.Items.trashTx([item.id]);
    const trashedItem = Zotero.Items.get(item.id);

    return {
      libraryID,
      itemID: item.id,
      itemKey: item.key,
      collectionCountBeforeTrash,
      trashed: !!(trashedItem && trashedItem.deleted),
    };
  },

  async processCreateAnnotationJob(config) {
    const libraryID = config.libraryID ?? Zotero.Libraries.userLibraryID;
    const attachment = getItemByLibraryAndKeyOrThrow(libraryID, config.itemKey, "Attachment item");
    if (!isAttachmentItem(attachment)) {
      throw new Error(`Item is not an attachment: libraryID=${libraryID}, key=${config.itemKey}`);
    }

    const annotationType = normalizeFieldValue(config.annotationType);
    if (!SUPPORTED_ANNOTATION_TYPES.includes(annotationType)) {
      throw new Error(`Unsupported annotationType: ${annotationType}`);
    }

    const page = config.page !== null && config.page !== undefined && config.page !== ""
      ? Number(config.page)
      : null;
    const fallbackPageIndex = Number.isInteger(page) ? page - 1 : null;
    const position = normalizeAnnotationPosition(config.position, fallbackPageIndex);
    const pageLabel = normalizeFieldValue(
      config.pageLabel || (page !== null ? page : position.pageIndex + 1)
    );
    const sortIndex = normalizeFieldValue(config.sortIndex || buildSyntheticAnnotationSortIndex(position));
    const key = normalizeFieldValue(config.annotationKey || Zotero.DataObjectUtilities.generateKey());
    const payload = {
      key,
      type: annotationType,
      comment: normalizeFieldValue(config.comment || ""),
      color: normalizeFieldValue(config.color || "#ffd400"),
      pageLabel,
      sortIndex,
      position,
      isExternal: !!config.isExternal,
      tags: asArray(config.tags || []).map((tag) => ({ name: normalizeFieldValue(tag) })),
    };

    if (["highlight", "underline"].includes(annotationType)) {
      payload.text = normalizeFieldValue(config.text || "");
    }

    const annotation = await Zotero.Annotations.saveFromJSON(attachment, payload, {});
    return {
      libraryID,
      attachmentID: attachment.id,
      attachmentKey: attachment.key,
      annotationID: annotation.id,
      annotationKey: annotation.key,
      annotationType,
      page,
      pageLabel: annotation.annotationPageLabel,
      sortIndex: annotation.annotationSortIndex,
      comment: annotation.annotationComment,
      text: annotation.annotationText || "",
      position: JSON.parse(annotation.annotationPosition),
    };
  },

  async processRunTransactionJob(config) {
    ensureArray(config.steps, "steps");
    const stepResults = [];
    for (let i = 0; i < config.steps.length; i++) {
      const rawStep = config.steps[i];
      ensurePlainObject(rawStep, `steps[${i}]`);
      const resolvedStep = resolveStepReferences(rawStep, stepResults);
      const stepAction = normalizeAction(resolvedStep.action);
      try {
        const stepResult = await this.dispatchAction({
          ...config,
          ...resolvedStep,
          action: stepAction,
          requestID: config.requestID ? `${config.requestID}-step-${i}` : null,
          requestSignature: `${config.requestSignature || "transaction"}:step:${i}`,
        });
        stepResults.push({
          stepIndex: i,
          action: stepAction,
          status: "success",
          ...stepResult,
        });
      }
      catch (err) {
        stepResults.push({
          stepIndex: i,
          action: stepAction,
          status: "error",
          error: String(err),
        });
        throw new TransactionStepError(
          `Transaction failed at step ${i} (${stepAction}): ${err}`,
          i,
          stepResults
        );
      }
    }

    return {
      stepCount: stepResults.length,
      stepResults,
    };
  },
};
