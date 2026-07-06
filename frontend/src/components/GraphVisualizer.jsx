import { useEffect, useRef } from "react";
import * as d3 from "d3";

export default function GraphVisualizer({ nodes, edges }) {
  const svgRef = useRef();

  useEffect(() => {
    if (!nodes.length) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const width = svgRef.current?.clientWidth || 800;
    const height = 420;
    svg.attr("viewBox", `0 0 ${width} ${height}`);

    const localNodes = nodes.map((n) => ({ ...n }));
    const localEdges = edges.map((e) => ({ ...e }));

    const simulation = d3
      .forceSimulation(localNodes)
      .force("link", d3.forceLink(localEdges).id((d) => d.id).distance(90))
      .force("charge", d3.forceManyBody().strength(-260))
      .force("center", d3.forceCenter(width / 2, height / 2));

    const color = (d) => {
      if (d.is_fraudster || d.is_compromised) return "#f43f5e"; // Rose
      if (d.is_circular) return "#fb923c"; // Orange
      if (d.is_layering) return "#f472b6"; // Pink
      if (d.is_mule || d.is_funnel || d.is_hub) return "#fbbf24"; // Amber
      if (d.type === "DEVICE") return "#a78bfa"; // Violet
      if (d.type === "ACCOUNT") return "#3b82f6"; // Cobalt
      return "#34d399"; // Emerald
    };

    const link = svg
      .selectAll(".link")
      .data(localEdges)
      .enter()
      .append("line")
      .attr("class", "link")
      .attr("stroke", (d) => {
        if (d.is_fraud_path) return "#f43f5e";
        const sourceId = typeof d.source === "object" ? d.source.id : d.source;
        const targetId = typeof d.target === "object" ? d.target.id : d.target;
        const srcNode = localNodes.find((n) => n.id === sourceId);
        const tgtNode = localNodes.find((n) => n.id === targetId);
        if (srcNode?.is_circular && tgtNode?.is_circular) return "#fb923c";
        if (srcNode?.is_layering && tgtNode?.is_layering) return "#f472b6";
        
        const srcFraud = srcNode?.is_fraudster;
        const tgtFraud = tgtNode?.is_fraudster;
        return srcFraud || tgtFraud ? "#f43f5e" : "#334155";
      })
      .attr("stroke-width", (d) => {
        if (d.is_fraud_path) return 3.0;
        const sourceId = typeof d.source === "object" ? d.source.id : d.source;
        const targetId = typeof d.target === "object" ? d.target.id : d.target;
        const srcNode = localNodes.find((n) => n.id === sourceId);
        const tgtNode = localNodes.find((n) => n.id === targetId);
        if (srcNode?.is_circular && tgtNode?.is_circular) return 2.5;
        if (srcNode?.is_layering && tgtNode?.is_layering) return 2.5;
        return 1.5;
      })
      .attr("stroke-dasharray", (d) => {
        if (d.is_fraud_path) return "4 2";
        const sourceId = typeof d.source === "object" ? d.source.id : d.source;
        const srcNode = localNodes.find((n) => n.id === sourceId);
        return srcNode?.is_fraudster ? "4 2" : "none";
      });

    const node = svg
      .selectAll(".node")
      .data(localNodes)
      .enter()
      .append("g")
      .attr("class", "node")
      .call(
        d3
          .drag()
          .on("start", (e, d) => {
            if (!e.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on("drag", (e, d) => {
            d.fx = e.x;
            d.fy = e.y;
          })
          .on("end", (e, d) => {
            if (!e.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          })
      );

    node
      .append("circle")
      .attr("r", (d) => {
        if (d.is_mule || d.is_circular || d.is_layering) return 13;
        return 10;
      })
      .attr("fill", color)
      .attr("stroke", (d) => {
        return "#0f172a";
      })
      .attr("stroke-width", (d) => {
        if (d.is_mule || d.is_circular || d.is_layering) return 2.0;
        return 1.5;
      });

    node
      .append("text")
      .text((d) => d.label)
      .attr("dy", -14)
      .attr("text-anchor", "middle")
      .attr("fill", "#cbd5e1")
      .attr("font-size", 9);

    simulation.on("tick", () => {
      link
        .attr("x1", (d) => d.source.x)
        .attr("y1", (d) => d.source.y)
        .attr("x2", (d) => d.target.x)
        .attr("y2", (d) => d.target.y);
      node.attr("transform", (d) => `translate(${d.x},${d.y})`);
    });

    return () => simulation.stop();
  }, [nodes, edges]);

  return <svg ref={svgRef} width="100%" height="420" />;
}
