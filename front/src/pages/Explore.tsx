import LiquidGlassExperience from '../components/liquid/LiquidGlassExperience'

interface ExploreProps {
  isActive?: boolean
}

export default function Explore({ isActive = true }: ExploreProps) {
  return <LiquidGlassExperience isActive={isActive} />
}
