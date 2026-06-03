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
      if (d.is_fraudster || d.is_compromised) return "#FF5C5C";
      if (d.type === "DEVICE") return "#B392F0";
      if (d.type === "ACCOUNT") return "#F7B32B";
      return "#5DE4C7";
    };

    const link = svg
      .selectAll(".link")
      .data(localEdges)
      .enter()
      .append("line")
      .attr("class", "link")
      .attr("stroke", (d) => {
        const sourceId = typeof d.source === "object" ? d.source.id : d.source;
        const targetId = typeof d.target === "object" ? d.target.id : d.target;
        const srcFraud = localNodes.find((n) => n.id === sourceId)?.is_fraudster;
        const tgtFraud = localNodes.find((n) => n.id === targetId)?.is_fraudster;
        return srcFraud || tgtFraud ? "#FF5C5C" : "#2A3344";
      })
      .attr("stroke-width", 1.5)
      .attr("stroke-dasharray", (d) => {
        const sourceId = typeof d.source === "object" ? d.source.id : d.source;
        const srcFraud = localNodes.find((n) => n.id === sourceId)?.is_fraudster;
        return srcFraud ? "4 2" : "none";
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
      .attr("r", 10)
      .attr("fill", color)
      .attr("stroke", "#0B0C10")
      .attr("stroke-width", 2);

    node
      .append("text")
      .text((d) => d.label)
      .attr("dy", -14)
      .attr("text-anchor", "middle")
      .attr("fill", "#94A3B8")
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
