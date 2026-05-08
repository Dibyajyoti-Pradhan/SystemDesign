import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Zap, BookOpen, Microscope } from "lucide-react";

interface DepthTabsProps {
  tldr: React.ReactNode;
  standard: React.ReactNode;
  deep: React.ReactNode;
}

export function DepthTabs({ tldr, standard, deep }: DepthTabsProps) {
  return (
    <Tabs defaultValue="tldr" className="w-full">
      <TabsList className="w-full justify-start">
        <TabsTrigger value="tldr"><Zap className="h-4 w-4 mr-1" /> TL;DR · 1 min</TabsTrigger>
        <TabsTrigger value="standard"><BookOpen className="h-4 w-4 mr-1" /> Standard · 5 min</TabsTrigger>
        <TabsTrigger value="deep"><Microscope className="h-4 w-4 mr-1" /> Deep · 15 min</TabsTrigger>
      </TabsList>
      <TabsContent value="tldr"><div className="prose-system">{tldr}</div></TabsContent>
      <TabsContent value="standard"><div className="prose-system">{standard}</div></TabsContent>
      <TabsContent value="deep"><div className="prose-system">{deep}</div></TabsContent>
    </Tabs>
  );
}
