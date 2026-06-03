import { useEffect, useState } from "react";

export default function useSSE(apiBase) {
  const [status, setStatus] = useState("connecting");
  const [lastEvent, setLastEvent] = useState(null);

  useEffect(() => {
    const eventSource = new EventSource(`${apiBase}/alerts/live`);

    eventSource.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data);
        setLastEvent(parsed);
        if (parsed.type === "CONNECTED") {
          setStatus("online");
        }
      } catch (e) {
        setStatus("offline");
      }
    };

    eventSource.onerror = () => {
      setStatus("offline");
      eventSource.close();
    };

    return () => eventSource.close();
  }, [apiBase]);

  return { status, lastEvent };
}
