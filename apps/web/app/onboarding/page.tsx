"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useToken } from "@/hooks/use-token";
import { ProgressIndicator } from "@/components/onboarding/progress-indicator";
import { RestaurantStep } from "@/components/onboarding/restaurant-step";
import { ProductsEquipmentStep } from "@/components/onboarding/products-equipment-step";
import { HACCPStep } from "@/components/onboarding/haccp-step";
import { PurchaseListStep } from "@/components/onboarding/purchase-list-step";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const TOTAL_STEPS = 4;

export default function OnboardingPage() {
  const router = useRouter();
  const token = useToken();
  const [step, setStep] = useState(1);
  const [restaurantId, setRestaurantId] = useState<string | null>(null);

  function goToDashboard() {
    if (restaurantId) {
      router.push(`/app/${restaurantId}/dashboard`);
    }
  }

  if (!token) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-muted-foreground">Loading...</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-3">
          <CardTitle>Welcome to ChefTrace</CardTitle>
          <ProgressIndicator current={step} total={TOTAL_STEPS} />
        </CardHeader>
        <CardContent>
          {step === 1 && (
            <RestaurantStep
              token={token}
              onComplete={(rid) => {
                setRestaurantId(rid);
                setStep(2);
              }}
            />
          )}
          {step === 2 && restaurantId && (
            <ProductsEquipmentStep
              restaurantId={restaurantId}
              token={token}
              onComplete={() => setStep(3)}
              onSkip={() => setStep(3)}
            />
          )}
          {step === 3 && (
            <HACCPStep
              onComplete={() => setStep(4)}
              onSkip={() => setStep(4)}
            />
          )}
          {step === 4 && restaurantId && (
            <PurchaseListStep
              restaurantId={restaurantId}
              token={token}
              onComplete={goToDashboard}
              onSkip={goToDashboard}
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
