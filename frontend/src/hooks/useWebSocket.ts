import { useEffect, useState, useCallback } from 'react';

export interface WebSocketMessage {
  type: string;
  timestamp: string;
  [key: string]: any;
}

export interface TaskUpdateMessage extends WebSocketMessage {
  type: 'task_update';
  task_id: string;
  status: string;
  progress?: number;
  message?: string;
  error?: string;
}

export interface ProjectUpdateMessage extends WebSocketMessage {
  type: 'project_update';
  project_id: string;
  status: string;
  progress?: number;
  message?: string;
}

export interface SystemNotificationMessage extends WebSocketMessage {
  type: 'system_notification';
  notification_type: string;
  title: string;
  message: string;
  level: 'info' | 'success' | 'warning' | 'error';
}

export interface ErrorNotificationMessage extends WebSocketMessage {
  type: 'error_notification';
  error_type: string;
  error_message: string;
  details?: any;
}

export interface TaskProgressUpdateMessage extends WebSocketMessage {
  type: 'task_progress_update';
  task_id?: string;
  project_id: string;
  status: 'running' | 'completed' | 'failed';
  progress: number;
  step_name: string;
  message?: string;
  snapshot?: boolean; // Mark whether it is a snapshot message
}

export type WebSocketEventMessage = 
  | TaskUpdateMessage 
  | ProjectUpdateMessage 
  | SystemNotificationMessage 
  | ErrorNotificationMessage
  | TaskProgressUpdateMessage;

interface UseWebSocketOptions {
  userId: string;
  onMessage?: (message: WebSocketEventMessage) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
}

export interface TaskSubscriptionStatus {
  user_id: string;
  subscribed_tasks: string[];
  total_subscriptions: number;
  active_channels: number;
}

// global scopeWebSocketConnection management
let globalWs: WebSocket | null = null;
let globalDesiredSubscriptions = new Set<string>();
let globalUserId: string | null = null;
let globalOnMessage: ((message: WebSocketEventMessage) => void) | null = null;
let globalOnConnect: (() => void) | null = null;
let globalOnDisconnect: (() => void) | null = null;
let globalOnError: ((error: Event) => void) | null = null;
let reconnectTimeoutRef: any = null;
let reconnectAttempts = 0;
const maxReconnectAttempts = 5;

// Heartbeat mechanism
let heartbeatInterval: any = null;
let heartbeatTimeout: any = null;
const HEARTBEAT_INTERVAL = 25000; // 25Send heartbeat once per second
const HEARTBEAT_TIMEOUT = 5000; // 5Did not receive within secondpongreconnection attempt in progress

// debouncing mechanism
let syncDebounceTimeout: number | null = null;
const SYNC_DEBOUNCE_DELAY = 300; // 300msdebounce

export const useWebSocket = (options: UseWebSocketOptions) => {
  const { userId, onMessage, onConnect, onDisconnect, onError } = options;
  const [isConnected, setIsConnected] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected' | 'error'>('disconnected');

  // Heartbeat related functions
  const startHeartbeat = useCallback(() => {
    if (heartbeatInterval) {
      clearInterval(heartbeatInterval);
    }
    
    heartbeatInterval = window.setInterval(() => {
      if (globalWs?.readyState === WebSocket.OPEN) {
        console.log('Sending heartbeat ping');
        globalWs.send(JSON.stringify({ type: 'ping' }));
        
        // configurationpongconnection timeout
        if (heartbeatTimeout) {
          clearTimeout(heartbeatTimeout);
        }
        heartbeatTimeout = window.setTimeout(() => {
          console.log('Heartbeat timeout, reconnecting');
          if (globalWs) {
            globalWs.close();
          }
        }, HEARTBEAT_TIMEOUT);
      }
    }, HEARTBEAT_INTERVAL);
  }, []);

  const stopHeartbeat = useCallback(() => {
    if (heartbeatInterval) {
      clearInterval(heartbeatInterval);
      heartbeatInterval = null;
    }
    if (heartbeatTimeout) {
      clearTimeout(heartbeatTimeout);
      heartbeatTimeout = null;
    }
  }, []);

  // Global connection function
  const ensureConnected = useCallback(() => {
    if (globalWs?.readyState === WebSocket.OPEN || globalWs?.readyState === WebSocket.CONNECTING) {
      return;
    }
    
    // If connection exists but user ID changed, close old connection
    if (globalWs && globalUserId !== userId) {
      console.log(`User ID changed: ${globalUserId} -> ${userId}, closing previous connection`);
      globalWs.close();
      globalWs = null;
    }

    setConnectionStatus('connecting');
    const wsUrl = `ws://localhost:8000/api/v1/ws/${userId}`;
    
    try {
      const ws = new WebSocket(wsUrl);
      globalWs = ws;
      globalUserId = userId;
      globalOnMessage = onMessage || null;
      globalOnConnect = onConnect || null;
      globalOnDisconnect = onDisconnect || null;
      globalOnError = onError || null;

      ws.onopen = () => {
        console.log('WebSocket connection established');
        setIsConnected(true);
        setConnectionStatus('connected');
        reconnectAttempts = 0;
        
        // starting heartbeat
        startHeartbeat();
        
        // Resubscribe to previous projects after reconnect
        if (globalDesiredSubscriptions.size > 0) {
          console.log('Resubscribing to projects after reconnect:', Array.from(globalDesiredSubscriptions));
          sendMessage({
            type: 'sync_subscriptions',
            project_ids: Array.from(globalDesiredSubscriptions)
          });
        }
        
        globalOnConnect?.();
      };

      ws.onmessage = (event) => {
        try {
          const data: WebSocketEventMessage = JSON.parse(event.data);
          console.log('Received WebSocket message:', data);
          
          // Handle pong response
          if ((data as any).type === 'pong') {
            console.log('Received heartbeat pong response');
            if (heartbeatTimeout) {
              clearTimeout(heartbeatTimeout);
              heartbeatTimeout = null;
            }
            return;
          }
          
          globalOnMessage?.(data);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      ws.onclose = (event) => {
        console.log('WebSocket connection closed:', event.code, event.reason);
        setIsConnected(false);
        setConnectionStatus('disconnected');
        
        // Stop heartbeat
        stopHeartbeat();
        
        globalOnDisconnect?.();

        // Enable automatic reconnect but limit reconnection attempts
        if (event.code !== 1000 && reconnectAttempts < maxReconnectAttempts) {
          reconnectAttempts++;
          const delay = Math.min(2000 * Math.pow(2, reconnectAttempts), 15000);
          console.log(`Will attempt reconnect in ${delay}ms (${reconnectAttempts}/${maxReconnectAttempts})`);
          
          reconnectTimeoutRef = setTimeout(() => {
            ensureConnected();
          }, delay);
        } else if (reconnectAttempts >= maxReconnectAttempts) {
          console.log('Reached maximum reconnect attempts, stopping reconnection');
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setConnectionStatus('error');
        globalOnError?.(error);
      };

    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
      setConnectionStatus('error');
    }
  }, [userId, onMessage, onConnect, onDisconnect, onError]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef) {
      clearTimeout(reconnectTimeoutRef);
      reconnectTimeoutRef = null;
    }
    
    if (globalWs) {
      globalWs.close(1000, 'User initiated disconnection');
      globalWs = null;
    }
    
    setIsConnected(false);
    setConnectionStatus('disconnected');
  }, []);

  const sendMessage = useCallback((message: any) => {
    if (globalWs?.readyState === WebSocket.OPEN) {
      globalWs.send(JSON.stringify(message));
      return true;
    }
    console.warn('WebSocket not connected, cannot send message');
    return false;
  }, []);

  const subscribeToTopic = useCallback((topic: string) => {
    return sendMessage({
      type: 'subscribe',
      topic
    });
  }, [sendMessage]);

  const unsubscribeFromTopic = useCallback((topic: string) => {
    return sendMessage({
      type: 'unsubscribe',
      topic
    });
  }, [sendMessage]);

  const ping = useCallback(() => {
    return sendMessage({
      type: 'ping'
    });
  }, [sendMessage]);

  const getStatus = useCallback(() => {
    return sendMessage({
      type: 'get_status'
    });
  }, [sendMessage]);

  const subscribeToTask = useCallback((taskId: string) => {
    return sendMessage({
      type: 'subscribe_task',
      task_id: taskId
    });
  }, [sendMessage]);

  const unsubscribeFromTask = useCallback((taskId: string) => {
    return sendMessage({
      type: 'unsubscribe_task',
      task_id: taskId
    });
  }, [sendMessage]);

  // Collection difference alignment subscription - core function (with debounce))
  const syncSubscriptions = useCallback((projectIds: string[]) => {
    const desired = new Set(projectIds);
    globalDesiredSubscriptions = desired;
    
    // Ensure connection
    ensureConnected();
    
    // Debounce handling
    if (syncDebounceTimeout) {
      clearTimeout(syncDebounceTimeout);
    }
    
    syncDebounceTimeout = window.setTimeout(() => {
      // Send synchronized subscription request
      if (globalWs?.readyState === WebSocket.OPEN) {
        console.log('Syncing subscribed projects:', Array.from(desired));
        sendMessage({
          type: 'sync_subscriptions',
          project_ids: Array.from(desired)
        });
      }
    }, SYNC_DEBOUNCE_DELAY);
    
    return { desired: Array.from(desired) };
  }, [sendMessage, ensureConnected]);

  // Batch subscribe/Unsubscription support
  const subscribeToMany = useCallback((channels: string[]) => {
    return sendMessage({
      type: 'subscribe_many',
      channels
    });
  }, [sendMessage]);

  const unsubscribeFromMany = useCallback((channels: string[]) => {
    return sendMessage({
      type: 'unsubscribe_many',
      channels
    });
  }, [sendMessage]);

  // Synchronized subscription set alignment interface
  const syncSubscriptionSet = useCallback((channels: string[]) => {
    return sendMessage({
      type: 'sync_subscriptions',
      channels
    });
  }, [sendMessage]);

  // auto-reconnect
  useEffect(() => {
    // Deferred connection - avoid re-rendering during component initialization
    const timer = setTimeout(() => {
      ensureConnected();
    }, 500);

    return () => {
      clearTimeout(timer);
      // Do not disconnect here - keep global connection
    };
  }, [userId, ensureConnected]);

  // Clean reconnect timer
  useEffect(() => {
    return () => {
      if (reconnectTimeoutRef) {
        clearTimeout(reconnectTimeoutRef);
      }
    };
  }, []);

  return {
    isConnected,
    connectionStatus,
    connect: ensureConnected,
    disconnect,
    sendMessage,
    subscribeToTopic,
    unsubscribeFromTopic,
    subscribeToTask,
    unsubscribeFromTask,
    syncSubscriptions,
    subscribeToMany,
    unsubscribeFromMany,
    syncSubscriptionSet,
    ping,
    getStatus
  };
}; 