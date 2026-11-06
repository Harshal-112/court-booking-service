import { cn } from "@/lib/utils";
import React, {
    useState,
    useRef,
    useEffect,
    forwardRef,
    useImperativeHandle,
    useMemo,
    useCallback,
    createContext,
    Children,
} from "react";

import { cva, type VariantProps } from "class-variance-authority";

import {
    ArrowRight,
    Mail,
    Gem,
    Lock,
    Eye,
    EyeOff,
    ArrowLeft,
    X,
    AlertCircle,
    PartyPopper,
    Loader,
} from "lucide-react";

import {
    AnimatePresence,
    motion,
    useInView,
    Variants,
    Transition,
} from "framer-motion";

import type { ReactNode } from "react";

import type {
    GlobalOptions as ConfettiGlobalOptions,
    CreateTypes as ConfettiInstance,
    Options as ConfettiOptions,
} from "canvas-confetti";

import confetti from "canvas-confetti";

import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";

// --- MAIN COMPONENT ---

interface AuthComponentProps {
    logo?: React.ReactNode;
    brandName?: string;
}

export const AuthComponent = ({
    logo = <DefaultLogo />,
    brandName = "CourtBook",
}: AuthComponentProps) => {
    const navigate = useNavigate();
    const { register } = useAuth();

    const [fullName, setFullName] = useState("");
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");

    const [showPassword, setShowPassword] = useState(false);
    const [showConfirmPassword, setShowConfirmPassword] = useState(false);

    const [authStep, setAuthStep] = useState("email");

    const [modalStatus, setModalStatus] = useState<
        "closed" | "loading" | "error" | "success"
    >("closed");

    const [modalErrorMessage, setModalErrorMessage] = useState("");

    const confettiRef = useRef<ConfettiRef>(null);
    const passwordInputRef = useRef<HTMLInputElement>(null);
    const confirmPasswordInputRef = useRef<HTMLInputElement>(null);

    // Validation

    const isFullNameValid =
        fullName.trim().length >= 2 &&
        fullName.trim().length <= 150;

    const isEmailValid =
        /^\S+@\S+\.\S+$/.test(email.trim());

    const isPasswordValid =
        password.length >= 8 &&
        password.length <= 128;

    const isConfirmPasswordValid =
        confirmPassword.length > 0 &&
        confirmPassword === password;

    // Confetti

    const fireSideCanons = () => {
        const fire = confettiRef.current?.fire;

        if (!fire) return;

        const defaults = {
            startVelocity: 30,
            spread: 360,
            ticks: 60,
            zIndex: 100,
        };

        const particleCount = 50;

        fire({
            ...defaults,
            particleCount,
            origin: { x: 0, y: 1 },
            angle: 60,
        });

        fire({
            ...defaults,
            particleCount,
            origin: { x: 1, y: 1 },
            angle: 120,
        });
    };

    // Submit registration to backend

    const handleFinalSubmit = async (
        e: React.FormEvent<HTMLFormElement>
    ) => {
        e.preventDefault();

        if (
            modalStatus !== "closed" ||
            authStep !== "confirmPassword"
        ) {
            return;
        }

        if (!isFullNameValid) {
            setModalErrorMessage(
                "Please enter a valid full name."
            );
            setModalStatus("error");
            return;
        }

        if (!isEmailValid) {
            setModalErrorMessage(
                "Please enter a valid email address."
            );
            setModalStatus("error");
            return;
        }

        if (!isPasswordValid) {
            setModalErrorMessage(
                "Password must contain between 8 and 128 characters."
            );
            setModalStatus("error");
            return;
        }

        if (password !== confirmPassword) {
            setModalErrorMessage(
                "Passwords do not match."
            );
            setModalStatus("error");
            return;
        }

        setModalStatus("loading");

        try {
            await register({
                full_name: fullName.trim(),
                email: email.trim(),
                password,
            });

            setModalStatus("success");
            fireSideCanons();
        } catch (error) {
            setModalErrorMessage(
                error instanceof Error
                    ? error.message
                    : "Registration failed. Please try again."
            );

            setModalStatus("error");
        }
    };

    // Move between signup steps

    const handleProgressStep = () => {
        if (authStep === "email") {
            if (isFullNameValid && isEmailValid) {
                setAuthStep("password");
            }
        } else if (authStep === "password") {
            if (isPasswordValid) {
                setAuthStep("confirmPassword");
            }
        }
    };

    const handleKeyDown = (
        e: React.KeyboardEvent<HTMLInputElement>
    ) => {
        if (e.key === "Enter") {
            e.preventDefault();
            handleProgressStep();
        }
    };

    const handleGoBack = () => {
        if (authStep === "confirmPassword") {
            setAuthStep("password");
            setConfirmPassword("");
        } else if (authStep === "password") {
            setAuthStep("email");
        }
    };

    const closeModal = () => {
        setModalStatus("closed");
        setModalErrorMessage("");
    };

    // Focus inputs when their steps become active

    useEffect(() => {
        let timer: ReturnType<typeof setTimeout> | undefined;

        if (authStep === "password") {
            timer = setTimeout(() => {
                passwordInputRef.current?.focus();
            }, 500);
        } else if (authStep === "confirmPassword") {
            timer = setTimeout(() => {
                confirmPasswordInputRef.current?.focus();
            }, 500);
        }

        return () => {
            if (timer) clearTimeout(timer);
        };
    }, [authStep]);

    // Modal

    const Modal = () => (
        <AnimatePresence>
            {modalStatus !== "closed" && (
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
                >
                    <motion.div
                        initial={{ scale: 0.9, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        exit={{ scale: 0.9, opacity: 0 }}
                        className="relative bg-card/80 border-4 border-border rounded-2xl p-8 w-full max-w-sm flex flex-col items-center gap-4 mx-2"
                    >
                        {(modalStatus === "error" ||
                            modalStatus === "success") && (
                                <button
                                    type="button"
                                    onClick={closeModal}
                                    className="absolute top-2 right-2 p-1 text-muted-foreground hover:text-foreground transition-colors"
                                    aria-label="Close modal"
                                >
                                    <X className="w-5 h-5" />
                                </button>
                            )}

                        {modalStatus === "error" && (
                            <>
                                <AlertCircle className="w-12 h-12 text-destructive" />

                                <p className="text-lg font-medium text-foreground text-center">
                                    {modalErrorMessage}
                                </p>

                                <GlassButton
                                    type="button"
                                    onClick={closeModal}
                                    size="sm"
                                    className="mt-4"
                                >
                                    Try Again
                                </GlassButton>
                            </>
                        )}

                        {modalStatus === "loading" && (
                            <TextLoop
                                interval={TEXT_LOOP_INTERVAL}
                                stopOnEnd={true}
                            >
                                {modalSteps.slice(0, -1).map((step, i) => (
                                    <div
                                        key={i}
                                        className="flex flex-col items-center gap-4"
                                    >
                                        {step.icon}

                                        <p className="text-lg font-medium text-foreground">
                                            {step.message}
                                        </p>
                                    </div>
                                ))}
                            </TextLoop>
                        )}

                        {modalStatus === "success" && (
                            <div className="flex flex-col items-center gap-4">
                                <PartyPopper className="w-12 h-12 text-green-500" />

                                <p className="text-lg font-medium text-foreground">
                                    Account created successfully!
                                </p>

                                <p className="text-sm text-muted-foreground text-center">
                                    Your CourtBook account is ready.
                                </p>

                                <GlassButton
                                    type="button"
                                    size="sm"
                                    onClick={() =>
                                        navigate("/dashboard", {
                                            replace: true,
                                        })
                                    }
                                >
                                    Continue
                                    <ArrowRight className="ml-2 h-4 w-4" />
                                </GlassButton>
                            </div>
                        )}
                    </motion.div>
                </motion.div>
            )}
        </AnimatePresence>
    );

    return (
        <div className="bg-background min-h-screen w-screen flex flex-col">
            {/* Keep your original component CSS here unchanged */}
            <style>{`
        /* KEEP THE COMPLETE ORIGINAL CSS STRING FROM YOUR EXISTING FILE HERE */
      `}</style>

            <Confetti
                ref={confettiRef}
                manualstart
                className="fixed top-0 left-0 w-full h-full pointer-events-none z-[999]"
            />

            <Modal />

            {/* Brand */}

            <div
                className={cn(
                    "fixed top-4 left-4 z-20 flex items-center gap-2",
                    "md:left-1/2 md:-translate-x-1/2"
                )}
            >
                {logo}

                <h1 className="text-base font-bold text-foreground">
                    {brandName}
                </h1>
            </div>

            {/* Signup background */}

            <div
                className={cn(
                    "flex w-full flex-1 h-full items-center justify-center bg-card",
                    "relative overflow-hidden"
                )}
            >
                <div className="absolute inset-0 z-0">
                    <GradientBackground />
                </div>

                <fieldset
                    disabled={modalStatus !== "closed"}
                    className="relative z-10 flex flex-col items-center gap-8 w-[280px] mx-auto p-4"
                >
                    {/* Step headings */}

                    <AnimatePresence mode="wait">
                        {authStep === "email" && (
                            <motion.div
                                key="email-content"
                                initial={{ y: 6, opacity: 0 }}
                                animate={{ y: 0, opacity: 1 }}
                                exit={{ opacity: 0 }}
                                transition={{
                                    duration: 0.3,
                                    ease: "easeOut",
                                }}
                                className="w-full flex flex-col items-center gap-4"
                            >
                                <BlurFade
                                    delay={0.25}
                                    className="w-full"
                                >
                                    <div className="text-center">
                                        <p className="font-serif font-light text-4xl sm:text-5xl md:text-6xl tracking-tight text-foreground">
                                            Get started with Us
                                        </p>
                                    </div>
                                </BlurFade>

                                <BlurFade delay={0.5}>
                                    <p className="text-sm font-medium text-muted-foreground">
                                        Create your CourtBook account
                                    </p>
                                </BlurFade>

                                <BlurFade delay={0.75} className="w-[300px]">
                                    <div className="flex items-center w-full gap-2 py-2">
                                        <hr className="w-full border-border" />

                                        <span className="text-xs font-semibold text-muted-foreground">
                                            SIGN UP
                                        </span>

                                        <hr className="w-full border-border" />
                                    </div>
                                </BlurFade>
                            </motion.div>
                        )}

                        {authStep === "password" && (
                            <motion.div
                                key="password-title"
                                initial={{ y: 6, opacity: 0 }}
                                animate={{ y: 0, opacity: 1 }}
                                exit={{ opacity: 0 }}
                                transition={{ duration: 0.3, ease: "easeOut" }}
                                className="w-full flex flex-col items-center text-center gap-4"
                            >
                                <BlurFade className="w-full">
                                    <p className="font-serif font-light text-4xl sm:text-5xl tracking-tight text-foreground">
                                        Create your password
                                    </p>
                                </BlurFade>

                                <BlurFade>
                                    <p className="text-sm font-medium text-muted-foreground">
                                        Your password must contain 8 to 128 characters.
                                    </p>
                                </BlurFade>
                            </motion.div>
                        )}

                        {authStep === "confirmPassword" && (
                            <motion.div
                                key="confirm-title"
                                initial={{ y: 6, opacity: 0 }}
                                animate={{ y: 0, opacity: 1 }}
                                exit={{ opacity: 0 }}
                                transition={{ duration: 0.3, ease: "easeOut" }}
                                className="w-full flex flex-col items-center text-center gap-4"
                            >
                                <BlurFade className="w-full">
                                    <p className="font-serif font-light text-4xl sm:text-5xl tracking-tight text-foreground">
                                        One Last Step
                                    </p>
                                </BlurFade>

                                <BlurFade>
                                    <p className="text-sm font-medium text-muted-foreground">
                                        Confirm your password to continue
                                    </p>
                                </BlurFade>
                            </motion.div>
                        )}
                    </AnimatePresence>

                    {/* Signup form */}

                    <form
                        onSubmit={handleFinalSubmit}
                        className="w-[300px] space-y-6"
                    >
                        <AnimatePresence mode="wait">
                            {authStep === "email" && (
                                <motion.div
                                    key="email-fields"
                                    initial={{ opacity: 0 }}
                                    animate={{ opacity: 1 }}
                                    exit={{ opacity: 0 }}
                                    className="w-full space-y-6"
                                >
                                    {/* Full name */}

                                    <div className="glass-input-wrap w-full">
                                        <div className="glass-input">
                                            <span className="glass-input-text-area" />

                                            <div className="relative z-10 flex items-center justify-center w-10 pl-2">
                                                <Gem className="h-5 w-5 text-foreground/80" />
                                            </div>

                                            <input
                                                type="text"
                                                placeholder="Full name"
                                                value={fullName}
                                                onChange={(e) =>
                                                    setFullName(e.target.value)
                                                }
                                                onKeyDown={handleKeyDown}
                                                minLength={2}
                                                maxLength={150}
                                                autoComplete="name"
                                                className="relative z-10 h-full w-0 flex-grow bg-transparent text-foreground placeholder:text-foreground/60 focus:outline-none"
                                            />
                                        </div>
                                    </div>

                                    {/* Email */}

                                    <div className="glass-input-wrap w-full">
                                        <div className="glass-input">
                                            <span className="glass-input-text-area" />

                                            <div className="relative z-10 flex items-center justify-center w-10 pl-2">
                                                <Mail className="h-5 w-5 text-foreground/80" />
                                            </div>

                                            <input
                                                type="email"
                                                placeholder="Email"
                                                value={email}
                                                onChange={(e) =>
                                                    setEmail(e.target.value)
                                                }
                                                onKeyDown={handleKeyDown}
                                                autoComplete="email"
                                                className="relative z-10 h-full w-0 flex-grow bg-transparent text-foreground placeholder:text-foreground/60 focus:outline-none"
                                            />

                                            <div
                                                className={cn(
                                                    "relative z-10 flex-shrink-0 overflow-hidden transition-all duration-300 ease-in-out",
                                                    isEmailValid && isFullNameValid
                                                        ? "w-10 pr-1"
                                                        : "w-0"
                                                )}
                                            >
                                                <GlassButton
                                                    type="button"
                                                    onClick={handleProgressStep}
                                                    size="icon"
                                                    aria-label="Continue"
                                                    contentClassName="text-foreground/80 hover:text-foreground"
                                                >
                                                    <ArrowRight className="w-5 h-5" />
                                                </GlassButton>
                                            </div>
                                        </div>
                                    </div>
                                </motion.div>
                            )}

                            {/* Password step */}

                            {authStep === "password" && (
                                <motion.div
                                    key="password-fields"
                                    initial={{ opacity: 0 }}
                                    animate={{ opacity: 1 }}
                                    exit={{ opacity: 0 }}
                                    className="w-full"
                                >
                                    <div className="glass-input-wrap w-full">
                                        <div className="glass-input">
                                            <span className="glass-input-text-area" />

                                            <div className="relative z-10 flex items-center justify-center w-10 pl-2">
                                                {isPasswordValid ? (
                                                    <button
                                                        type="button"
                                                        aria-label="Toggle password visibility"
                                                        onClick={() =>
                                                            setShowPassword(!showPassword)
                                                        }
                                                        className="p-2 text-foreground/80"
                                                    >
                                                        {showPassword ? (
                                                            <EyeOff className="w-5 h-5" />
                                                        ) : (
                                                            <Eye className="w-5 h-5" />
                                                        )}
                                                    </button>
                                                ) : (
                                                    <Lock className="h-5 w-5 text-foreground/80" />
                                                )}
                                            </div>

                                            <input
                                                ref={passwordInputRef}
                                                type={showPassword ? "text" : "password"}
                                                placeholder="Password"
                                                value={password}
                                                onChange={(e) =>
                                                    setPassword(e.target.value)
                                                }
                                                onKeyDown={handleKeyDown}
                                                autoComplete="new-password"
                                                className="relative z-10 h-full w-0 flex-grow bg-transparent text-foreground placeholder:text-foreground/60 focus:outline-none"
                                            />

                                            <div
                                                className={cn(
                                                    "relative z-10 flex-shrink-0 overflow-hidden transition-all duration-300 ease-in-out",
                                                    isPasswordValid ? "w-10 pr-1" : "w-0"
                                                )}
                                            >
                                                <GlassButton
                                                    type="button"
                                                    onClick={handleProgressStep}
                                                    size="icon"
                                                    aria-label="Continue"
                                                    contentClassName="text-foreground/80 hover:text-foreground"
                                                >
                                                    <ArrowRight className="w-5 h-5" />
                                                </GlassButton>
                                            </div>
                                        </div>
                                    </div>
                                </motion.div>
                            )}

                            {/* Confirm password step */}

                            {authStep === "confirmPassword" && (
                                <motion.div
                                    key="confirm-password-field"
                                    initial={{ opacity: 0 }}
                                    animate={{ opacity: 1 }}
                                    exit={{ opacity: 0 }}
                                    className="w-full"
                                >
                                    <div className="glass-input-wrap w-full">
                                        <div className="glass-input">
                                            <span className="glass-input-text-area" />

                                            <div className="relative z-10 flex items-center justify-center w-10 pl-2">
                                                {isConfirmPasswordValid ? (
                                                    <button
                                                        type="button"
                                                        aria-label="Toggle confirm password visibility"
                                                        onClick={() =>
                                                            setShowConfirmPassword(
                                                                !showConfirmPassword
                                                            )
                                                        }
                                                        className="p-2 text-foreground/80"
                                                    >
                                                        {showConfirmPassword ? (
                                                            <EyeOff className="w-5 h-5" />
                                                        ) : (
                                                            <Eye className="w-5 h-5" />
                                                        )}
                                                    </button>
                                                ) : (
                                                    <Lock className="h-5 w-5 text-foreground/80" />
                                                )}
                                            </div>

                                            <input
                                                ref={confirmPasswordInputRef}
                                                type={
                                                    showConfirmPassword
                                                        ? "text"
                                                        : "password"
                                                }
                                                placeholder="Confirm Password"
                                                value={confirmPassword}
                                                onChange={(e) =>
                                                    setConfirmPassword(e.target.value)
                                                }
                                                autoComplete="new-password"
                                                className="relative z-10 h-full w-0 flex-grow bg-transparent text-foreground placeholder:text-foreground/60 focus:outline-none"
                                            />

                                            <div
                                                className={cn(
                                                    "relative z-10 flex-shrink-0 overflow-hidden transition-all duration-300 ease-in-out",
                                                    isConfirmPasswordValid
                                                        ? "w-10 pr-1"
                                                        : "w-0"
                                                )}
                                            >
                                                <GlassButton
                                                    type="submit"
                                                    size="icon"
                                                    aria-label="Finish signup"
                                                    contentClassName="text-foreground/80 hover:text-foreground"
                                                >
                                                    <ArrowRight className="w-5 h-5" />
                                                </GlassButton>
                                            </div>
                                        </div>
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>

                        {/* Back button */}

                        {authStep !== "email" && (
                            <button
                                type="button"
                                onClick={handleGoBack}
                                className="mt-4 flex items-center gap-2 text-sm text-foreground/70 hover:text-foreground transition-colors"
                            >
                                <ArrowLeft className="w-4 h-4" />
                                Go back
                            </button>
                        )}
                    </form>

                    {/* Login link */}

                    <p className="relative z-10 text-sm text-muted-foreground">
                        Already have an account?{" "}
                        <Link
                            to="/login"
                            className="font-semibold text-foreground underline underline-offset-4"
                        >
                            Sign in
                        </Link>
                    </p>
                </fieldset>
            </div>
        </div>
    );
};