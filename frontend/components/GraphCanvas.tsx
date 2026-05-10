"use client";

import { useEffect, useMemo, useRef } from "react";
import cytoscape, { Core, ElementDefinition } from "cytoscape";
import type { KnowledgeGraph, KnowledgeNode } from "@/types/domain";

interface GraphCanvasProps {
  graph: KnowledgeGraph;
  selectedNode?: KnowledgeNode | null;
  search: string;
  onSelect: (node: KnowledgeNode) => void;
}

const palette = ["#0f766e", "#8a704f", "#455a64", "#9a4f43", "#486a51", "#6f6474", "#63724f"];

export function GraphCanvas({ graph, search, onSelect }: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const cyRef = useRef<Core | null>(null);
  const nodeMap = useMemo(() => new Map(graph.nodes.map((node) => [node.id, node])), [graph.nodes]);

  useEffect(() => {
    if (!containerRef.current) return;

    const elements: ElementDefinition[] = [
      ...graph.nodes.map((node, index) => ({
        data: {
          id: node.id,
          label: node.name,
          frequency: node.frequency,
          color: palette[index % palette.length],
          source: node.source_textbooks?.[0] ?? node.textbook_id
        }
      })),
      ...graph.edges.map((edge) => ({
        data: {
          id: edge.id,
          source: edge.source,
          target: edge.target,
          label: edge.relation_type
        }
      }))
    ];

    cyRef.current?.destroy();
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
            "overlay-opacity": 0
          }
        },
        {
          selector: "edge",
          style: {
            width: 1.2,
            "line-color": "#b8beb6",
            "target-arrow-color": "#b8beb6",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            label: "data(label)",
            "font-size": 9,
            color: "#747f7a"
          }
        },
        {
          selector: ".dimmed",
          style: { opacity: 0.16 }
        },
        {
          selector: ".matched",
          style: { "border-color": "#1f2926", "border-width": 4 }
        }
      ]
    });

    cy.on("tap", "node", (event) => {
      const node = nodeMap.get(event.target.id());
      if (node) onSelect(node);
    });
    cyRef.current = cy;

    return () => cy.destroy();
  }, [graph, nodeMap, onSelect]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.elements().removeClass("dimmed matched");
    const query = search.trim().toLowerCase();
    if (!query) return;
    const matched = cy.nodes().filter((node) => {
      const label = String(node.data("label")).toLowerCase();
      return label.includes(query);
    });
    cy.elements().addClass("dimmed");
    matched.removeClass("dimmed").addClass("matched");
    matched.connectedEdges().removeClass("dimmed");
  }, [search]);

  if (!graph.nodes.length) {
    return (
      <div className="empty-graph">
        <strong>等待知识图谱</strong>
        <span>上传并解析教材后，点击“构建图谱”即可生成可交互节点。</span>
      </div>
    );
  }

  return <div ref={containerRef} className="graph-canvas" />;
}
