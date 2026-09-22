import React, { useEffect, useState, useCallback } from 'react';
import { Card, Row, Col, Statistic, Button } from 'antd';
import TaskProgress from './TaskProgress';
import { NotificationList } from './NotificationList';
import { useNotifications } from '../hooks/useNotifications';
import { useProjectStore } from '../store/useProjectStore';

interface RealTimeStatusProps {
  userId: string;
  projectId?: string;
}

export const RealTimeStatus: React.FC<RealTimeStatusProps> = ({ userId, projectId }) => {
  const currentProject = useProjectStore((state) => state.currentProject);
  
  const [tasks, setTasks] = useState<
    Array<{
      id: string;
      status: string;
      progress: number;
      message: string;
      updatedAt: string;
      project_id?: string;
    }>
  >([]);
  const [loading, setLoading] = useState(false);
  
  // Directly use simple state management, without complexHook
  const loadProjectTasks = useCallback(async (projectId: string) => {
    console.log('Loading project tasks:', projectId);
    setLoading(true);
    try {
      const response = await fetch(`/api/v1/tasks/project/${projectId}`);
      console.log('API response status:', response.status);
      
      if (response.ok) {
        const data = await response.json();
        const projectTasks = data.items || [];
        console.log('Retrieved tasks count:', projectTasks.length);
        
        // Format tasks
        const formattedTasks = projectTasks.map((task: any) => ({
          id: task.id,
          status: task.status,
          progress: task.progress || 0,
          message: task.name || `Task ${task.id}`,
          updatedAt: task.created_at || task.updated_at || new Date().toISOString(),
          project_id: task.project_id
        }));
        
        setTasks(formattedTasks);
      } else {
        console.error('API call failed:', response.status, response.statusText);
      }
    } catch (error) {
      console.error('Failed to load project tasks:', error);
    } finally {
      setLoading(false);
      console.log('Tasks loaded successfully');
    }
  }, []);

  const {
    notifications,
    unreadCount,
    markAsRead,
    removeNotification,
    markAllAsRead,
    clearAll: clearAllNotifications
  } = useNotifications();

  // Loading project tasks
  useEffect(() => {
    const activeProjectId = projectId || currentProject?.id;
    if (!activeProjectId) {
      setTasks([]);
      return;
    }
    console.log('Loading project tasks for active project:', activeProjectId);
    loadProjectTasks(activeProjectId);
  }, [projectId, currentProject?.id, loadProjectTasks]);

  return (
    <div style={{ padding: 16 }}>
      <Row gutter={[16, 16]}>
        {/* Statistics information */}
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="Total task count"
              value={tasks.length}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="Loading status"
              value={loading ? 'Loading...' : 'Done'}
              valueStyle={{ color: loading ? '#52c41a' : '#999' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="Unread notifications"
              value={unreadCount}
              valueStyle={{ color: unreadCount > 0 ? '#ff4d4f' : '#999' }}
            />
          </Card>
        </Col>

        {/* Task progress */}
        <Col span={12}>
          <Card 
            title="Task progress" 
            size="small"
            extra={
              <Button size="small" onClick={() => setTasks([])}>
                Clear
              </Button>
            }
          >
            <div style={{ maxHeight: 300, overflowY: 'auto' }}>
              {tasks.length === 0 ? (
                <div style={{ textAlign: 'center', padding: 20, color: '#999' }}>
                  No tasks yet
                </div>
              ) : (
                tasks.map((task) => (
                  <TaskProgress 
                    key={task.id} 
                    projectId={task.project_id || userId}
                    taskId={task.id}
                    status={task.status === 'running' ? 'processing' : task.status}
                  />
                ))
              )}
            </div>
          </Card>
        </Col>

        {/* Notification list */}
        <Col span={12}>
          <NotificationList
            notifications={notifications}
            unreadCount={unreadCount}
            onMarkAsRead={markAsRead}
            onRemove={removeNotification}
            onMarkAllAsRead={markAllAsRead}
            onClearAll={clearAllNotifications}
            maxHeight={300}
          />
        </Col>
      </Row>
    </div>
  );
}; 
