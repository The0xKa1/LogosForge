"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import cytoscape, { Core, ElementDefinition } from "cytoscape";
import { Search } from "lucide-react";
import type { KnowledgeGraph, KnowledgeNode } from "@/types/domain";

interface GraphCanvasProps {
  graph: KnowledgeGraph;
  selectedNode?: KnowledgeNode | null;
  search: string;
  onSelect: (node: KnowledgeNode | null) => void;
  onSearchChange?: (search: string) => void;
}

const palette = ["#0f766e", "#8a704f", "#455a64", "#9a4f43", "#486a51", "#6f6474", "#63724f"];

// 关系类型配置
const relationConfig = {
  prerequisite: { color: "#2196f3", label: "前置知识", dash: "solid" },
  parallel: { color: "#9e9e9e", label: "并列关系", dash: "dashed" },
  contains: { color: "#4caf50", label: "包含关系", dash: "solid" },
  applies_to: { color: "#ff9800", label: "应用场景", dash: "dotted" },
};

export function GraphCanvas({ graph, search, onSelect, onSearchChange }: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const cyRef = useRef<Core | null>(null);
  const nodeMap = useMemo(() => new Map(graph.nodes.map((node) => [node.id, node])), [graph.nodes]);

  // 来源过滤器状态
  const [sourceFilter, setSourceFilter] = useState<string | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  // 获取所有来源教材
  const sources = useMemo(() => {
    const sourceSet = new Set<string>();
    graph.nodes.forEach((node) => {
      const source = node.source_textbooks?.[0] ?? node.textbook_id;
      sourceSet.add(source);
    });
    return Array.from(sourceSet).sort();
  }, [graph.nodes]);

  // 处理节点选择
  const handleNodeSelect = useCallback(
    (nodeId: string | null) => {
      setSelectedNodeId(nodeId);
      if (nodeId) {
        const node = nodeMap.get(nodeId);
        if (node) onSelect(node);
      } else {
        onSelect(null);
      }
    },
    [nodeMap, onSelect]
  );

  useEffect(() => {
    if (!containerRef.current) return;

    const elements: ElementDefinition[] = [
      ...graph.nodes.map((node, index) => ({
        data: {
          id: node.id,
          label: node.name,
          frequency: node.frequency,
          color: palette[index % palette.length],
          source: node.source_textbooks?.[0] ?? node.textbook_id,
          category: node.category,
        },
      })),
      ...graph.edges.map((edge) => ({
        data: {
          id: edge.id,
          source: edge.source,
          target: edge.target,
          label: edge.relation_type,
          description: edge.description,
          relation_type: edge.relation_type,
        },
      })),
    ];

    cyRef.current?.destroy();

    // 确保容器尺寸已计算完毕
    const raf = requestAnimationFrame(() => {
    if (!containerRef.current) return;
    const cy = cytoscape({
      container: containerRef.current,
      elements,
      layout: { name: "cose", animate: false, padding: 56, nodeRepulsion: () => 9800 },
      wheelSensitivity: 0.18,
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            "background-color": "data(color)",
            color: "#1f2926",
            width: "mapData(frequency, 1, 8, 38, 86)",
            height: "mapData(frequency, 1, 8, 38, 86)",
            "font-size": 11,
            "font-weight": 600,
            "text-valign": "bottom",
            "text-margin-y": 8,
            "border-width": 2,
            "border-color": "#f6f4ee",
            "overlay-opacity": 0,
          },
        },
        {
          selector: "edge",
          style: {
            width: 1.5,
            "line-color": "#b8beb6",
            "target-arrow-color": "#b8beb6",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            label: "data(label)",
            "font-size": 9,
            color: "#747f7a",
          },
        },
        // 选中节点样式
        {
          selector: "node:selected",
          style: {
            "border-color": "#1f2926",
            "border-width": 4,
            "background-color": "#1f2926",
            color: "#ffffff",
          },
        },
        // 高亮节点样式（选中节点的关联节点）
        {
          selector: ".highlighted",
          style: {
            "border-color": "#0f766e",
            "border-width": 3,
            opacity: 1,
          },
        },
        // 暗化样式
        {
          selector: ".dimmed",
          style: { opacity: 0.15 },
        },
        // 搜索匹配样式
        {
          selector: ".matched",
          style: { "border-color": "#ff9800", "border-width": 4, opacity: 1 },
        },
        // 过滤隐藏样式
        {
          selector: ".filtered",
          style: { display: "none" },
        },
      ],
    });

    // 设置边的样式（根据关系类型）
    cy.edges().forEach((edge) => {
      const relationType = edge.data("relation_type");
      const config = relationConfig[relationType as keyof typeof relationConfig];
      if (config) {
        edge.style({
          "line-color": config.color,
          "target-arrow-color": config.color,
          "line-style": config.dash,
        });
      }
    });

    // 节点点击事件
    cy.on("tap", "node", (event) => {
      const nodeId = event.target.id();
      handleNodeSelect(nodeId);
    });

    // 点击空白区域取消选择
    cy.on("tap", (event) => {
      if (event.target === cy) {
        handleNodeSelect(null);
      }
    });

    cyRef.current = cy;
    });

    return () => {
      cancelAnimationFrame(raf);
      cyRef.current?.destroy();
    };
  }, [graph, handleNodeSelect]);

  // 搜索高亮效果
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    cy.elements().removeClass("dimmed matched");
    const query = search.trim().toLowerCase();

    if (!query) return;

    const matched = cy.nodes().filter((node) => {
      const label = String(node.data("label")).toLowerCase();
      const category = String(node.data("category")).toLowerCase();
      return label.includes(query) || category.includes(query);
    });

    cy.elements().addClass("dimmed");
    matched.removeClass("dimmed").addClass("matched");
    matched.connectedEdges().removeClass("dimmed");
  }, [search]);

  // 选中节点高亮效果
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    // 清除之前的高亮
    cy.elements().removeClass("highlighted");

    if (!selectedNodeId) return;

    const selectedNode = cy.getElementById(selectedNodeId);
    if (selectedNode.length === 0) return;

    // 高亮选中节点的关联节点和边
    const neighborhood = selectedNode.neighborhood().union(selectedNode);
    neighborhood.addClass("highlighted");

    // 暗化其他元素
    cy.elements().not(neighborhood).addClass("dimmed");
    neighborhood.removeClass("dimmed");
  }, [selectedNodeId]);

  // 来源过滤效果
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    cy.nodes().removeClass("filtered");

    if (sourceFilter) {
      cy.nodes().forEach((node) => {
        const source = node.data("source");
        if (source !== sourceFilter) {
          node.addClass("filtered");
        }
      });
    }
  }, [sourceFilter]);

  if (!graph.nodes.length) {
    return (
      <div className="empty-graph">
        <strong>等待知识图谱</strong>
        <span>上传并解析教材后，点击"构建图谱"即可生成可交互节点。</span>
      </div>
    );
  }

  return (
    <div className="graph-container">
      {/* 搜索框 */}
      {onSearchChange && (
        <div className="graph-search">
          <Search size={16} />
          <input
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="搜索知识点并高亮节点"
          />
        </div>
      )}

      {/* 图例和过滤器 */}
      <div className="graph-controls">
        {/* 关系类型图例 */}
        <div className="legend">
          <span className="legend-title">关系类型：</span>
          {Object.entries(relationConfig).map(([type, config]) => (
            <div key={type} className="legend-item">
              <span
                className="legend-line"
                style={{
                  backgroundColor: config.color,
                  borderStyle: config.dash === "dashed" ? "dashed" : config.dash === "dotted" ? "dotted" : "solid",
                }}
              />
              <span>{config.label}</span>
            </div>
          ))}
        </div>

        {/* 来源过滤器 */}
        {sources.length > 1 && (
          <div className="source-filter">
            <span>来源筛选：</span>
            <button
              className={!sourceFilter ? "active" : ""}
              onClick={() => setSourceFilter(null)}
            >
              全部
            </button>
            {sources.map((source) => (
              <button
                key={source}
                className={sourceFilter === source ? "active" : ""}
                onClick={() => setSourceFilter(source === sourceFilter ? null : source)}
              >
                {source}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* 图谱画布 */}
      <div ref={containerRef} className="graph-canvas" />

      {/* 节点详情侧栏 */}
      {selectedNodeId && nodeMap.has(selectedNodeId) && (
        <NodeDetailSidebar
          node={nodeMap.get(selectedNodeId)!}
          onClose={() => handleNodeSelect(null)}
          relatedNodes={getRelatedNodes(selectedNodeId, graph)}
        />
      )}
    </div>
  );
}

// 获取关联节点
function getRelatedNodes(nodeId: string, graph: KnowledgeGraph): KnowledgeNode[] {
  const relatedIds = new Set<string>();

  graph.edges.forEach((edge) => {
    if (edge.source === nodeId) {
      relatedIds.add(edge.target);
    } else if (edge.target === nodeId) {
      relatedIds.add(edge.source);
    }
  });

  return graph.nodes.filter((node) => relatedIds.has(node.id));
}

// 节点详情侧栏组件
function NodeDetailSidebar({
  node,
  onClose,
  relatedNodes,
}: {
  node: KnowledgeNode;
  onClose: () => void;
  relatedNodes: KnowledgeNode[];
}) {
  return (
    <div className="node-detail-sidebar">
      <div className="sidebar-header">
        <h3>{node.name}</h3>
        <button onClick={onClose} className="close-btn">
          ✕
        </button>
      </div>

      <div className="sidebar-content">
        <div className="node-info">
          <div className="info-item">
            <span className="label">类型</span>
            <span className="value">{node.category}</span>
          </div>
          <div className="info-item">
            <span className="label">章节</span>
            <span className="value">{node.chapter}</span>
          </div>
          <div className="info-item">
            <span className="label">页码</span>
            <span className="value">第 {node.page} 页</span>
          </div>
          <div className="info-item">
            <span className="label">频次</span>
            <span className="value">{node.frequency} 次</span>
          </div>
          <div className="info-item">
            <span className="label">来源</span>
            <span className="value">{node.source_textbooks.join("、") || node.textbook_id}</span>
          </div>
        </div>

        <div className="node-definition">
          <h4>定义</h4>
          <p>{node.definition}</p>
        </div>

        {node.evidence && node.evidence !== node.definition && (
          <div className="node-evidence">
            <h4>证据</h4>
            <p>{node.evidence}</p>
          </div>
        )}

        {relatedNodes.length > 0 && (
          <div className="related-nodes">
            <h4>关联知识点 ({relatedNodes.length})</h4>
            <ul>
              {relatedNodes.map((related) => (
                <li key={related.id}>
                  <span className="related-name">{related.name}</span>
                  <span className="related-category">{related.category}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
