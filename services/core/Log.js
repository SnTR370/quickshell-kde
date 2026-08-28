.pragma library

const LogLevel = {
    DEBUG: 0,
    INFO: 1,
    WARN: 2,
    ERROR: 3
};

let currentLevel = LogLevel.DEBUG;

function format(levelStr, tag, msg) {
    const timestamp = new Date().toISOString().substring(11, 19);
    return `[${timestamp}] [${levelStr}] [${tag}] ${msg}`;
}

function debug(tag, msg) {
    if (currentLevel <= LogLevel.DEBUG) {
        console.log(format("DEBUG", tag, msg));
    }
}

function info(tag, msg) {
    if (currentLevel <= LogLevel.INFO) {
        console.log(format("INFO ", tag, msg));
    }
}

function warn(tag, msg) {
    if (currentLevel <= LogLevel.WARN) {
        console.warn(format("WARN ", tag, msg));
    }
}

function error(tag, msg) {
    if (currentLevel <= LogLevel.ERROR) {
        console.error(format("ERROR", tag, msg));
    }
}
