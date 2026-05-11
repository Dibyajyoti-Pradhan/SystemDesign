import pino from "pino";

const isDev = process.env.NODE_ENV !== "production";

const logger = isDev
  ? pino({ level: "info" }, pino.destination({ dest: process.stdout.fd, sync: true }))
  : pino({
      level: "info",
      transport: {
        target: "pino-pretty",
        options: { colorize: true },
      },
    });

export default logger;
