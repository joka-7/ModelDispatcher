// react-dom/client's createRoot only wraps updates in `act` automatically
// when this flag is set — without it every render/act pair in these tests
// prints a spurious "not configured to support act" warning.
(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
